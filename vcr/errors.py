class CannotOverwriteExistingCassetteException(Exception):
    def __init__(self, *args, **kwargs):
        self.cassette = kwargs["cassette"]
        self.failed_request = kwargs["failed_request"]
        message = self._get_message(kwargs["cassette"], kwargs["failed_request"])
        super(CannotOverwriteExistingCassetteException, self).__init__(message)

    def _get_message(self, cassette, failed_request):
        """Get the final message related to the exception"""
        # Get the similar requests in the cassette that
        # have match the most with the request.
        best_matches = cassette.find_requests_with_most_matches(failed_request)
        # Build a comprehensible message to put in the exception.
        best_matches_msg = ""
        for best_match in best_matches:
            request, _, failed_matchers_assertion_msgs = best_match
            best_matches_msg += "Similar request found : (%r).\n" % request
            for failed_matcher, assertion_msg in failed_matchers_assertion_msgs:
                best_matches_msg += "Matcher failed : %s\n" "%s\n" % (
                    failed_matcher,
                    assertion_msg,
                )
        return (
            "Can't overwrite existing cassette (%r) in "
            "your current record mode (%r).\n"
            "No match for the request (%r) was found.\n"
            "%s"
            % (cassette._path, cassette.record_mode, failed_request, best_matches_msg)
        )


class UnhandledHTTPRequestError(KeyError):
    """Raised when a cassette does not contain the request we want."""
    pass
