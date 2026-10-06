The authoritative restart point is [docs/CURRENT_WORK.md (line 37)](C:/Users/leamanjr/projects/abrex/docs/CURRENT_WORK.md:37). It records the missing key, authorization boundary, exact command, limits, and what I do afterward. [direct-extraction-baseline.md (line 42)](C:/Users/leamanjr/projects/abrex/docs/direct-extraction-baseline.md:42) contains the detailed run contract.
When GPT-6 Luna API access is ready:
1. Make OPENAI_API_KEY available to the Codex process. Do not paste it into chat. If you add it as a Windows environment variable, restart Codex so it inherits the variable. This follows the official OpenAI API quickstart.
2. Send this exact restart prompt:
Continue the experiment campaign. I authorize sending the 20 T062 biomedical passages to the Azure OpenAI Responses API using GPT-6 Luna under the documented $0.05 hard cap. All Azure OpenAI enviroment variables are available in the Codex environment: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS, and AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS.

You do not need to create the cache or run directory. Their absence only proves that no scientific API run has occurred:
- The response cache will be created automatically at evidence/campaign-2026-10/milestone-b/direct-extraction-cache.jsonl.
- Predictions, evaluation, reports, and the run manifest will be created automatically under .artifacts/campaign-2026-10/direct-extraction/.
- I will run the command, validate usage and outputs, analyze all errors, and prepare any necessary review packet.
The only immediate blockers are explicit authorization, a usable API key, and GPT-6 Luna availability for that API project. I will not substitute another model.
Later Milestone C dependencies—not actions you need to take now—are:
- approving the final 120-passage review workload and proposed success thresholds after seeing Milestone B;
- authorizing any required live TypeSafe scientific-data requests;
- running Ab3P/PLOD on a fresh Linux server because this machine lacks the required WSL runtime;
- completing the tested prediction-blind review packet.
I’ll prepare those as concrete, tested handoffs when they become current rather than asking you to do advance setup.

The pending campaign run now targets the Azure OpenAI v1 Responses API. It sends the API key in Azure’s api-key header and uses your deployment name as the request’s model. I updated the run documentation and pre-freeze inventory to match. Microsoft’s Responses guide documents that route.
Set exactly these five environment variables in the PowerShell session where you run Abrex:
Variable	Set it to
AZURE_OPENAI_ENDPOINT	Your resource URL, such as https://RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY	Your resource’s API key
AZURE_OPENAI_DEPLOYMENT	Your deployment name
AZURE_OPENAI_INPUT_USD_PER_MILLION_TOKENS	Your applicable Azure input-token price
AZURE_OPENAI_OUTPUT_USD_PER_MILLION_TOKENS	Your applicable Azure output-token price

Azure GPT-6 Luna pricing seems to be:
  - Input: $0.10 per million tokens
  - Output: $0.50 per million tokens

The two price values are required because the run retains its $0.05 configured cost cap; the earlier OpenAI prices do not establish your Azure rates. Check the rates for your deployment and billing arrangement against Azure pricing. No API-version variable is needed for Azure’s v1 route. Microsoft’s endpoint guide confirms its implicit versioning.
Before running, confirm that the deployment and region support the Responses API, strict JSON Schema Structured Outputs, and medium reasoning. The 20 biomedical passages also need authorization to be sent to this Azure resource. The exact setup and run command are in [direct-extraction-baseline.md (line 46)](C:/Users/leamanjr/projects/abrex/docs/direct-extraction-baseline.md:46).
