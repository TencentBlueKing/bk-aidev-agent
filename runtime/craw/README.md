# AIDEV Craw PaaS Runtime

Concrete, shared Dockerfile runtime for AIDEV collaborative agents. PaaS clones this directory directly; it is not a cookiecutter template.

All environment-specific values are injected by `bk-aidev` when `create_ai_agent_app` is called:

- `CRAW_BASE_IMAGE` through `bkapp_spec.build_config.docker_build_args`
- AIDEV gateway, stage, upstream origin, API Gateway settings, and maintainers through `bkapp_spec.configuration.env`

The public source therefore contains no private registry, internal hostname, application credential, or user token.
