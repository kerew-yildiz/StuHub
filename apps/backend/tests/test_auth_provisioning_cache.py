"""`get_tenant_id`'nin profil sağlama önbelleği — her istekte gereksiz DB round-trip'ini
önler (2026-09-05 perf turu). JWT/DB'yi taklit eder, yalnızca önbellek davranışını sınar.
"""

from src import auth


async def test_ensure_profile_only_called_once_per_tenant(monkeypatch):
    calls: list[str] = []

    async def fake_ensure_profile(tenant_id: str, email: str) -> None:
        calls.append(tenant_id)

    monkeypatch.setattr(auth.settings, "database_url", "postgresql://fake")
    monkeypatch.setattr(auth, "_decode_token", lambda token: {"sub": "user-1", "email": "a@b.com"})
    monkeypatch.setattr(auth, "_ensure_profile", fake_ensure_profile)
    auth._provisioned.clear()

    tenant_1 = await auth.get_tenant_id("Bearer tok")
    tenant_2 = await auth.get_tenant_id("Bearer tok")

    assert tenant_1 == tenant_2 == "user-1"
    assert calls == ["user-1"]  # ikinci istekte tekrar çağrılmadı


async def test_different_tenants_each_provisioned_once(monkeypatch):
    calls: list[str] = []

    async def fake_ensure_profile(tenant_id: str, email: str) -> None:
        calls.append(tenant_id)

    subs = iter(["user-a", "user-b", "user-a"])
    monkeypatch.setattr(auth.settings, "database_url", "postgresql://fake")
    monkeypatch.setattr(auth, "_decode_token", lambda token: {"sub": next(subs)})
    monkeypatch.setattr(auth, "_ensure_profile", fake_ensure_profile)
    auth._provisioned.clear()

    await auth.get_tenant_id("Bearer tok")
    await auth.get_tenant_id("Bearer tok")
    await auth.get_tenant_id("Bearer tok")

    assert calls == ["user-a", "user-b"]  # user-a ikinci kez sağlanmadı
