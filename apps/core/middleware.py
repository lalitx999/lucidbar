from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """
    Adds a Content-Security-Policy header to every response.

    Django 5.2 has no built-in CSP support, and the policy is a single static
    string, so a tiny middleware is simpler than adding a dependency. The policy
    only allows our own origin, which enforces the "no external CDN" rule.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = getattr(settings, "CSP_POLICY", "")
        self.permissions = getattr(settings, "PERMISSIONS_POLICY", "")

    def __call__(self, request):
        response = self.get_response(request)
        if self.policy and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.policy
        # Browser features the site may use: only the camera, for door scanning.
        if self.permissions and "Permissions-Policy" not in response:
            response["Permissions-Policy"] = self.permissions
        return response
