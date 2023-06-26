class CannotOverwriteExistingCassetteException(Exception):
    def __init__(self, *args, **kwargs):
        self.cassette = kwargs["cassette"]
        self.failed_request = kwargs["failed_request"]
        message = self._get_message(kwargs["cassette"], kwargs["failed_request"])
        super().__init__(message)

    @staticmethod
    def _get_message(cassette, failed_request):
        """Get the final message related to the exception"""
        # Get the similar requests in the cassette that
        # have match the most with the request.
        best_matches = cassette.find_requests_with_most_matches(failed_request)
        if best_matches:
            # Build a comprehensible message to put in the exception.
            best_matches_msg = (
                f"Found {len(best_matches)} similar requests "
                f"with {len(best_matches[0][2])} different matcher(s) :\n"
            )

            for idx, best_match in enumerate(best_matches, start=1):
                request, succeeded_matchers, failed_matchers_assertion_msgs = best_match
                best_matches_msg += (
                    f"\n{idx} - ({request!r}).\n"
                    f"Matchers succeeded : {succeeded_matchers}\n"
                    "Matchers failed :\n"
                )
                for failed_matcher, assertion_msg in failed_matchers_assertion_msgs:
                    best_matches_msg += f"{failed_matcher} - assertion failure :\n{assertion_msg}\n"
        else:
            best_matches_msg = "No similar requests, that have not been played, found."
        return (
            f"Can't overwrite existing cassette ({cassette._path!r}) in "
            f"your current record mode ({cassette.record_mode!r}).\n"
            f"No match for the request ({failed_request!r}) was found.\n"
            f"{best_matches_msg}"
        )


class UnhandledHTTPRequestError(KeyError):
    """Raised when a cassette does not contain the request we want."""
