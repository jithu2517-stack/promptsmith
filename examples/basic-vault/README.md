# Basic vault example

Run this from the repository root after installing PromptSmith:

```bash
promptsmith --vault-dir examples/basic-vault init --force
promptsmith --vault-dir examples/basic-vault create greeting \
  --system "You are a concise assistant." \
  --user "Say hello to {{name}}."
promptsmith --vault-dir examples/basic-vault run greeting --var name=Ada
```

The default `mock` provider makes this safe to try without an API key. For OpenAI
or Anthropic, install the matching optional dependency and set the provider's API
key in your environment. Do not store credentials in this example directory.
