# surgicalm/middleware.py
def debug_origin(get_response):
    """
    TEMP middleware that logs the Origin header for POST requests.
    Remove it once CSRF/Origin issues are solved.
    """
    def middleware(request):
        if request.method == "POST":
            origin = request.META.get("HTTP_ORIGIN", "<none>")
            print(f"[DEBUG-ORIGIN] {request.path}  ->  {origin}")
        return get_response(request)

    return middleware