"""
Azure Functions Python v2 entry point. The worker imports exactly this
one file at the deployment root - every other function is only surfaced
by registering its Blueprint here. Keep this file minimal (no heavy
imports beyond the blueprints themselves) since it runs on every cold
start.
"""
import azure.durable_functions as df
import azure.functions as func

from api.http_bp import bp as http_bp
from orchestrator.saga_bp import bp as saga_bp

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)
app.register_functions(http_bp)
app.register_functions(saga_bp)
