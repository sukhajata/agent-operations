---
name: microsoft-agents
description: Microsoft Agent Framework (MAF) best practices for this codebase. Use when designing, implementing, or reviewing any code that uses Microsoft.Agents.AI — including agent setup, session persistence, middleware, context providers, tool approval, and architecture decisions.
---

# Microsoft Agent Framework — Best Practices

This skill covers the correct architecture and API usage for Microsoft Agent Framework (MAF) v1.10+, as used in this codebase. References: [MAF samples](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples).

## Architecture: Controller → Agent

The correct layering is **Controller → Agent**. The agent is responsible for:
- Conversation state (via session serialization)
- Context injection (adding context in addition to the request — via context providers)
- Tools (including tool approval)
- Middleware (guardrails, logging)

**Do not** add a service layer or adapter layer purely to wrap the agent. These layers only add value when there is genuine business logic that is separate from the AI conversation. If the agent drives the decisions, extra layers are overhead without benefit.

### When extra layers are justified
- A service layer is justified when there is non-agentic business logic (state machines, multi-step orchestration, IDOR checks) that is distinct from the AI conversation.
- An adapter/repository layer is justified when the interface needs to be mockable for unit tests and the business logic is complex enough to warrant isolated testing.
- If the agent drives the decisions and the surrounding code is thin glue, collapse it into the controller.

### Responsibility split (quick rule)

- **Tools**: invoke external capabilities or perform side effects the model cannot do itself.
- **Middleware**: enforce cross-cutting policy on every run or tool call (guardrails, logging, policy).
- **Context providers**: inject dynamic context/tools before each model call.
- **Session persistence**: keep multi-turn state across requests (`chat history` + `StateBag`).

If behavior must run regardless of path, it belongs in middleware. If behavior is request/session context for reasoning, it belongs in context providers and/or `StateBag`.

---

## Key Classes (Microsoft.Agents.AI)

| Class | Purpose |
|---|---|
| `ChatClientAgent` | MAF agent built on `IChatClient`. Create via `chatClient.AsAIAgent(options)`. |
| `AIAgent` | Abstract base. Return type of `.Build()`. Use for middleware-wrapped agents. |
| `AgentSession` | Per-conversation state: chat history + `StateBag`. |
| `AgentResponse` | Result of `RunAsync`. Contains `Messages` (including tool approval requests). |
| `ChatClientAgentOptions` | Config: `Instructions`, `ChatHistoryProvider`, `AIContextProviders`. |
| `AIContextProvider` | Injects both messages **and** tools into the agent pipeline. |
| `MessageAIContextProvider` | Injects messages only (simpler base class). |

---

## Session Persistence

Use `SerializeSessionAsync` / `DeserializeSessionAsync` to persist sessions between HTTP requests. Both methods are public on `AIAgent` in v1.10+, though not documented in XML docs.

```csharp
// Serialize after run
JsonElement serialized = await agent.SerializeSessionAsync(session, null, ct);
await cache.TryUpsertAsync(cacheKey, serialized.GetRawText(), ttl);

// Deserialize on next request
var (found, json) = await cache.TryGetAsync<string>(cacheKey);
using var doc = JsonDocument.Parse(json!);
AgentSession session = await agent.DeserializeSessionAsync(doc.RootElement, null, ct);
```

**Do not** use the `ConversationId` pattern (`((ChatClientAgentSession)session).ConversationId`) as a workaround — `SerializeSessionAsync` is the correct API.

### StateBag — session-scoped shared state

`session.StateBag` stores typed values that survive serialization. Use this to pass context (DbId, ClientId, original request) to tools and context providers without threading values through every method signature.

```csharp
// Store on session creation
session.StateBag.SetValue(nameof(GenerationContext), new GenerationContext(dbId, clientId, request));

// Read anywhere that has access to InvokingContext.Session or AgentSession
var ctx = context.Session.StateBag.GetValue<GenerationContext>(nameof(GenerationContext));
```

### When session persistence is required

Session persistence is required when any of these are true:
- Multi-turn interaction spans multiple HTTP requests.
- Tool approval is requested in one request and approved in a later request.
- Session state must survive process restarts or multiple instances.
- You need conversation-scoped runtime values (tracking IDs, selected options, context snapshots).

You can skip persistence for one-shot request/response flows with no approvals and no resume behavior.

`StateBag` guidance:
- Prefer IDs and compact snapshots over large mutable objects.
- Re-fetch mutable external data when freshness matters.
- Keep security/tenant identifiers server-owned (do not trust model-provided values).

---

## Context Providers

Context providers inject information into the agent pipeline before each LLM call. Prefer `AIContextProvider` over `MessageAIContextProvider` when you also need to inject tools.

### AIContextProvider (messages + tools)

```csharp
internal sealed class BrandAndToolsContextProvider(
    IBrandContextService brandContextService,
    IAssetGenerationService assetGenerationService) : AIContextProvider
{
    protected override async ValueTask<AIContext> ProvideAIContextAsync(
        InvokingContext context, CancellationToken ct = default)
    {
        var genCtx = context.Session.StateBag.GetValue<GenerationContext>(nameof(GenerationContext));
        var brand = await brandContextService.GetBrandContextAsync(genCtx.DbId, genCtx.ClientId, ct);

        return new AIContext
        {
            Messages = [ new ChatMessage(ChatRole.User, brand?.ToBrandContextString() ?? string.Empty) ],
            Tools =
            [
                new ApprovalRequiredAIFunction(
                    AIFunctionFactory.Create(
                        async ([Description("Final optimised prompt")] string prompt) =>
                            await assetGenerationService.TriggerImageGenerationWithPromptAsync(
                                genCtx.DbId, genCtx.ClientId, prompt, genCtx.OriginalRequest, ct),
                        "GenerateImage",
                        "Generate the image using the refined prompt"))
            ]
        };
    }
}
```

### Preventing context provider messages from accumulating in chat history

Context providers run on every turn. Exclude their messages from stored chat history or they accumulate:

```csharp
var options = new ChatClientAgentOptions
{
    ChatHistoryProvider = new InMemoryChatHistoryProvider(new InMemoryChatHistoryProviderOptions
    {
        StorageInputRequestMessageFilter = messages => messages.Where(m =>
            m.GetAgentRequestMessageSourceType() != AgentRequestMessageSourceType.AIContextProvider &&
            m.GetAgentRequestMessageSourceType() != AgentRequestMessageSourceType.ChatHistory)
    }),
    AIContextProviders = [ new BrandAndToolsContextProvider(...) ]
};
```

### Register via options or builder

```csharp
// Option A: via ChatClientAgentOptions (preferred — survives serialization context)
var agent = chatClient.AsAIAgent(options);  // options includes AIContextProviders

// Option B: via builder
var agent = baseAgent.AsBuilder()
    .UseAIContextProviders(new MyContextProvider())
    .Build();
```

### When to use a context provider

Use `AIContextProvider` when you need one or both of:
- Dynamic context messages on every turn (tenant/account/brand/workflow state).
- Dynamic tool availability (feature flags, permissions, state-dependent tools).

Use `MessageAIContextProvider` only when you inject messages and no tools.

Avoid context providers for global policies (guardrails, tracing, authz) — those belong in middleware.

---

## Tool Approval (Human-in-the-Loop)

Wrap an `AIFunction` in `ApprovalRequiredAIFunction` to require approval before execution. The agent returns `ToolApprovalRequestContent` in the response instead of executing the tool.

> **Note:** In `Microsoft.Extensions.AI` 9.x the type was called `FunctionApprovalRequestContent`. It was renamed to `ToolApprovalRequestContent` in 10.x. This codebase uses 10.6.0.

```csharp
// Register with approval required (typically done in AIContextProvider.ProvideAIContextAsync)
AIFunction generateImage = AIFunctionFactory.Create(MyGenerateFunc, "GenerateImage", "...");
AIFunction approvalRequired = new ApprovalRequiredAIFunction(generateImage);
```

### Detecting a pending approval

```csharp
AgentResponse response = await agent.RunAsync(message, session, null, ct);

var pending = response.Messages
    .SelectMany(m => m.Contents)
    .OfType<ToolApprovalRequestContent>()
    .FirstOrDefault();

if (pending != null)
{
    // Store in StateBag for the next HTTP request (ToolApprovalRequestContent is JSON-serializable via MAF's source-gen context)
    session.StateBag.SetValue("PendingApproval", pending);
    // Serialize and persist session, return "awaiting approval" response to client
}
```

### Approving on the next request

```csharp
// Deserialize session, retrieve stored approval
var pending = session.StateBag.GetValue<ToolApprovalRequestContent>("PendingApproval")
    ?? throw new InvalidOperationException("No pending approval.");

// CreateResponse signature: (bool approved, string? reason = null)
var approvalMessage = new ChatMessage(ChatRole.User, [pending.CreateResponse(true)]);
var response = await agent.RunAsync(approvalMessage, session, null, ct);
```

### When to use tools

Use tools when the agent needs capabilities outside text generation:
- External I/O (DB/API/search/file/storage)
- Side effects (create/send/publish/enqueue)
- Deterministic domain logic that must not be hallucinated
- High-risk or expensive actions requiring approval

Avoid tools when the task is pure conversational generation with no external dependency.

Security note: keep server-owned context (tenant IDs, db IDs, auth context) in server state (`StateBag`, closures), not model-authored tool arguments.

---

## Middleware

Apply middleware via `AsBuilder().Use(...)`. Middleware runs on every `RunAsync` call.

### Agent-level middleware (intercepts full runs)

```csharp
var agent = baseAgent.AsBuilder()
    .Use(
        runFunc: async (messages, session, options, innerAgent, ct) =>
        {
            // Pre-processing (e.g. guardrails)
            var userText = messages.ToList().LastOrDefault(m => m.Role == ChatRole.User)?.Text ?? string.Empty;
            await guardrailService.ScreenAsync(userText, ct);
            return await innerAgent.RunAsync(messages, session, options, ct);
        },
        runStreamingFunc: null)
    .Build();
```

### Function invocation middleware (intercepts tool calls)

Different signature — wraps individual function invocations:

```csharp
async ValueTask<object?> LoggingMiddleware(
    AIAgent agent,
    FunctionInvocationContext context,
    Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next,
    CancellationToken ct)
{
    // context.Function.Name, context.Arguments available
    var result = await next(context, ct);
    return result;
}
```

### Shared state in middleware

Shared state between middleware and tools is a closure-captured object, not a special MAF type:

```csharp
var sharedState = new MySharedState();

var agent = baseAgent.AsBuilder()
    .Use(runFunc: async (messages, session, options, innerAgent, ct) =>
    {
        sharedState.SomeValue = "set by middleware";
        return await innerAgent.RunAsync(messages, session, options, ct);
    }, runStreamingFunc: null)
    .Build();

// Tool also captures sharedState via closure
AIFunction tool = AIFunctionFactory.Create(() => sharedState.SomeValue, "GetValue", "...");
```

For state that must survive serialization, use `session.StateBag` instead.

### When to use middleware

Use middleware for behavior that must be centrally enforced:
- Guardrails/content filtering
- Telemetry/logging correlation
- Policy checks and allow/deny wrappers
- Cross-cutting error handling and normalization

Do not place core business orchestration in middleware.

### Agent-level vs function-invocation middleware

- **Agent-level (`runFunc`)**: sees `messages` + `session`; best for run-wide policy/guardrails.
- **Function-invocation**: sees function metadata + arguments; best for per-tool validation/auditing.

If tool execution needs session-scoped data, capture `InvokingContext.Session.StateBag` during tool registration or use run middleware to populate shared state.

---

## Creating the Agent

```csharp
IChatClient chatClient = new ResponsesClient(apiKey).AsIChatClient(model);

var built = new ChatClientBuilder(chatClient)
    .UseOpenTelemetry(sourceName: "...", configure: o => o.EnableSensitiveData = true)
    .Build();

var options = new ChatClientAgentOptions
{
    Name = "MyAgent",
    ChatOptions = new ChatOptions { Instructions = systemPrompt },
    AIContextProviders = [ new MyContextProvider() ],
};

ChatClientAgent agent = built.AsAIAgent(options);
```

To add middleware, wrap the result:

```csharp
AIAgent agentWithMiddleware = agent.AsBuilder()
    .Use(runFunc: GuardrailMiddleware, runStreamingFunc: null)
    .Build();
```

Note: `ChatClientAgent` (returned by `AsAIAgent`) is needed for `CreateSessionAsync` and `SerializeSessionAsync`. Call these on the original `ChatClientAgent`, not on the middleware-wrapped `AIAgent`.

---

## Guardrails

Guardrails belong in agent-level middleware. This ensures they run on every invocation regardless of call site:

```csharp
var agent = baseAgent.AsBuilder()
    .Use(
        runFunc: async (messages, session, options, innerAgent, ct) =>
        {
            var userText = messages.ToList().LastOrDefault(m => m.Role == ChatRole.User)?.Text ?? string.Empty;
            await guardrailService.ScreenAsync(userText, ct);
            return await innerAgent.RunAsync(messages, session, options, ct);
        },
        runStreamingFunc: null)
    .Build();
```

---

## Decision Guide: Tool vs Middleware vs Context Provider vs Session

| Need | Primary mechanism | Why |
|---|---|---|
| Agent must call external capability | Tool | Explicit capability boundary the model can invoke |
| Behavior must run on every invocation | Middleware | Centralized and consistent enforcement |
| Inject dynamic context before model call | Context provider | Per-turn context composition |
| Continue state across requests/turns | Session persistence + `StateBag` | Resume, approval, and multi-turn continuity |

Common combinations:
- **Tool + Approval + Session**: high-risk side effects.
- **Context provider + Session**: stable per-conversation context without argument threading.
- **Middleware + Tool**: enforce guardrails/policy before tool execution.

Anti-patterns:
- Copying guardrails into many tool closures instead of middleware.
- Storing oversized mutable domain objects in `StateBag` by default.
- Encoding business workflow entirely in middleware.
- Adding wrapper service layers that only forward agent calls.

---

## Samples Reference

When MAF documentation is unclear or the XML docs are missing, check the official samples:

- **Middleware + context providers**: [`Agent_Step11_Middleware`](https://github.com/microsoft/agent-framework/blob/main/dotnet/samples/02-agents/Agents/Agent_Step11_Middleware/Program.cs)
- **AIContextProvider + StateBag + serialization**: [`Agent_Step17_AdditionalAIContext`](https://github.com/microsoft/agent-framework/blob/main/dotnet/samples/02-agents/Agents/Agent_Step17_AdditionalAIContext/Program.cs)
- **Tool approval**: [`Agent_Step01_UsingFunctionToolsWithApprovals`](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents/Agents/Agent_Step01_UsingFunctionToolsWithApprovals)
- **All samples**: [`dotnet/samples/02-agents`](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/02-agents)

When in doubt about an API, fetch the raw sample file rather than relying on documentation or training data — MAF's public API surface is ahead of its XML docs.
