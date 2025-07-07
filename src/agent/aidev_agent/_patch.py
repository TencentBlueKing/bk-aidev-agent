import jinja2  # noqa
import jinja2.sandbox  # noqa

# monkey patch jinja2
jinja2.Environment = jinja2.sandbox.SandboxedEnvironment
