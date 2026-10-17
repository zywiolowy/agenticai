# AI usage policy

## Data classification
- Red: patient data, medical images, secrets, credentials. Never send to any external LLM provider.
- Amber: source code and internal documents. Only through the internal gateway, to approved models.
- Green: public information. Any approved model.

## Approved models
- `local-chat` (self-hosted on our own GPU) is the default for internal code and documents.
- `cloud-chat` may be used for green data, or for amber data only through the gateway with zero data retention.

## Rules
All AI calls go through the LiteLLM gateway so they are logged, budgeted and traced in Langfuse.
Agents get read-only tools by default. Any write action needs human approval.
