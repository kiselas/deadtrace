from dishka import Provider, Scope, provide

from .domain import EVENTS, LegacyService, Repository, Service


class AppProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def repository(self) -> Repository:
        EVENTS.append("provider.repository")
        return Repository()

    @provide(scope=Scope.REQUEST)
    def service(self, repository: Repository) -> Service:
        EVENTS.append("provider.service")
        return Service(repository)

    @provide(scope=Scope.REQUEST)
    def legacy(self) -> LegacyService:
        EVENTS.append("provider.legacy")
        return LegacyService()
