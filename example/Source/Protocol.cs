// The Clear BSD License
//
// Copyright (c) 2026 Ian Hylton
// All rights reserved.


using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;


namespace CmdRouter.Example.Source;


// Mirrors `_UniversalContext.INTERNAL_JSON_CONTRACT` (full shape).
// Serve mode implies `json_out`, so every stderr line has exactly these keys
// with `null` for absent values instead of omitted keys:
//
//   ok, code, kind, input, command, value, parsed_args, error, message, exception
//
// `suggestions` only exists on the narrow watchdog fallback the router prints
// when the control layer could not emit its own line; it is kept optional here
// so this one record parses both shapes.
public sealed record RouterResponse {
    [JsonPropertyName("ok")] public bool Ok { get; init; }

    [JsonPropertyName("code")] public string? Code { get; init; }

    [JsonPropertyName("kind")] public string? Kind { get; init; }

    [JsonPropertyName("input")] public JsonNode? Input { get; init; }

    [JsonPropertyName("command")] public string? Command { get; init; }

    [JsonPropertyName("value")] public JsonNode? Value { get; init; }

    [JsonPropertyName("parsed_args")] public Dictionary<string, JsonNode?>? ParsedArgs { get; init; }

    [JsonPropertyName("error")] public RouterError? Error { get; init; }

    [JsonPropertyName("message")] public string? Message { get; init; }

    [JsonPropertyName("exception")] public string? Exception { get; init; }

    [JsonPropertyName("suggestions")] public List<string>? Suggestions { get; init; }

    public List<string>? Hints { get { return Error?.Suggestions ?? Suggestions; } }

    // One human line per protocol line: success shows the action value,
    // plain input shows the passthrough, failures show code/kind + hints.
    public string Describe() {
        switch(Ok) {
            case true when string.Equals(Kind, "INPUT", StringComparison.OrdinalIgnoreCase):
                return $"passthrough value={Json(Input)}";

            case true:
                return $"command=/{Command} value={Json(Value)} args={Json(ParsedArgs)}";
        }

        var hints  = Hints is { Count: > 0 } ? $" hints=[{string.Join(", ", Hints)}]" : "";
        var detail = Message ?? Exception ?? Error?.Message ?? "?";

        return $"{Code}/{Kind}: {detail}{hints}";
    }

    private static string Json(object? node) =>
        node switch {
            null                            => "null",
            JsonNode n                      => n.ToJsonString(),
            Dictionary<string, JsonNode?> d => JsonSerializer.Serialize(d),
            _                               => node.ToString() ?? "null",
        };
}


// Mirrors `ParseError.to_dict()`: fixed keys, `null` for absent values.
public sealed record RouterError { // ignore suggestion, do not make this abstract
    [JsonPropertyName("kind")] public string? Kind { get; init; }

    [JsonPropertyName("token_index")] public int? TokenIndex { get; init; }

    [JsonPropertyName("expected")] public List<string>? Expected { get; init; }

    [JsonPropertyName("token")] public JsonNode? Token { get; init; }

    [JsonPropertyName("suggestions")] public List<string>? Suggestions { get; init; }

    [JsonPropertyName("message")] public string? Message { get; init; }

    [JsonPropertyName("partial_args")] public Dictionary<string, JsonNode?>? PartialArgs { get; init; }

    [JsonPropertyName("code")] public string? Code { get; init; }
}


public static class RouterProtocol {
    private static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = false };

    public static RouterResponse Parse(string line) =>
        JsonSerializer.Deserialize<RouterResponse>(line, Options)
     ?? throw new JsonException("router response deserialized to null");
}
