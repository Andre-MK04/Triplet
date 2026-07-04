class ProviderError(RuntimeError):
    """Base class for all flight-provider failures."""


class ProviderConfigError(ProviderError):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderApiError(ProviderError):
    pass


class ProviderRateLimitError(ProviderApiError):
    pass


class ProviderNoResultsError(ProviderApiError):
    pass


class ProviderMappingError(ProviderError):
    pass
