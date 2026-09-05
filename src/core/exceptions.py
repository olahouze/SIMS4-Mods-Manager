class Sims4ManagerError(Exception):
    """Exception de base pour SIMS4-Mods-Manager."""
    pass


class ApiClientError(Sims4ManagerError):
    """Erreur levée lors d'un échec d'appel REST à l'API locale."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class ApiConnectionError(ApiClientError):
    """Erreur levée lorsque le serveur API local est inaccessible."""
    pass


class ProviderError(Sims4ManagerError):
    """Erreur de base pour les opérations de providers distants."""
    pass


class ProviderScrapeError(ProviderError):
    """Erreur survenue lors du scraping du catalogue distant."""
    pass


class ModDownloadError(ProviderError):
    """Erreur lors du téléchargement d'un fichier de mod."""
    pass


class ModArchiveError(Sims4ManagerError):
    """Erreur survenue lors de l'extraction ou de la compression d'archives."""
    pass


class DependencyResolutionError(Sims4ManagerError):
    """Erreur lors de la résolution de dépendances."""
    pass
