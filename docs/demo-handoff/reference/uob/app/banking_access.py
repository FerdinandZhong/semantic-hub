"""Server-owned caller scopes. Missing platform enforcement never grants execution."""
import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from fastapi import HTTPException
from .connectors import ConnectionFailure


@dataclass(frozen=True)
class Caller:
    subject: str
    role: str
    revision: str
    model_sha256: str
    fields: dict
    policy_sha256: str=''

    def permits(self, source, field):
        return field in self.fields.get(source, ())


def authenticate(path, authorization):
    """Opaque bearer credentials map to identity only through the server policy."""
    try:
        raw=Path(path).read_bytes();policy=json.loads(raw)
        if set(policy)!={'schema','revision','principals'} or policy['schema']!='uob.access.v1':raise ValueError()
        if not isinstance(policy['revision'],str) or not policy['revision'] or not isinstance(policy['principals'],list):raise ValueError()
        subjects=set();tokens=set()
        for entry in policy['principals']:
            if set(entry)!={'subject','role','token_sha256','model_sha256','fields'}:raise ValueError()
            if entry['role'] not in {'operator','analyst'}:raise ValueError()
            if not isinstance(entry['subject'],str) or not entry['subject'].strip() or len(entry['subject'])>128:raise ValueError()
            for key in ['token_sha256','model_sha256']:
                if not isinstance(entry[key],str) or len(entry[key])!=64 or any(c not in '0123456789abcdef' for c in entry[key]):raise ValueError()
            if entry['subject'] in subjects or entry['token_sha256'] in tokens:raise ValueError()
            subjects.add(entry['subject']);tokens.add(entry['token_sha256'])
            if not isinstance(entry['fields'],dict):raise ValueError()
            for source,fields in entry['fields'].items():
                if not isinstance(source,str) or not source or not isinstance(fields,list) or any(not isinstance(f,str) or not f or f=='*' for f in fields):raise ValueError()
    except (OSError,ValueError,TypeError,KeyError):
        raise HTTPException(503,'Caller policy is unavailable or invalid.') from None
    if not authorization.startswith('Bearer ') or not authorization[7:]:raise HTTPException(401,'A verified caller credential is required.')
    token=hashlib.sha256(authorization[7:].encode()).hexdigest()
    entry=next((entry for entry in policy['principals'] if secrets.compare_digest(entry['token_sha256'],token)),None)
    if entry is None:raise HTTPException(401,'Caller authentication failed.')
    return Caller(entry['subject'],entry['role'],policy['revision'],entry['model_sha256'],entry['fields'],hashlib.sha256(raw).hexdigest())


def recheck_policy(settings,caller):
    if not settings.access_policy_file:return
    try:current=hashlib.sha256(Path(settings.access_policy_file).read_bytes()).hexdigest()
    except OSError:raise ConnectionFailure('Caller policy is unavailable.') from None
    if caller is None or not secrets.compare_digest(current,caller.policy_sha256):
        raise ConnectionFailure('Caller policy changed. Authenticate again before planning or execution.')


@dataclass(frozen=True)
class PlatformDecision:
    allowed: bool=False
    identity_enforced: bool=False
    effective_subject: str=''


class UnavailablePlatform:
    def authorize(self, settings, caller, sources):return PlatformDecision()
    def execute(self, settings, sql, caller):raise ConnectionFailure('Caller-enforced Trino execution is unavailable.')


def require_execution(settings, platform, caller, sources):
    if caller is None:raise ConnectionFailure('Live banking execution requires a verified caller and platform enforcement adapter.')
    recheck_policy(settings,caller)
    try:decision=platform.authorize(settings,caller,tuple(sorted(sources)))
    except Exception:raise ConnectionFailure('Platform authorization could not be verified.') from None
    if not isinstance(decision,PlatformDecision) or not decision.allowed or not decision.identity_enforced or decision.effective_subject!=caller.subject:
        raise ConnectionFailure('The platform did not confirm execution enforcement for this caller. No shared-account fallback is permitted.')
    # Reuse the sibling Helios boundary; restrictions cannot manufacture platform access.
    from .semantics import helios_modules
    helios_modules(settings.helios_path)
    from helios_core.identity import Principal,PrincipalKind
    from helios_core.data_authorization import DataPolicy,DataResource,DataAction,PlatformDataDecision
    class ConfirmedPlatform:
        def can_access(self,principal,resource,action):
            return PlatformDataDecision(decision.allowed,decision.identity_enforced)
    principal=Principal('uob-server-policy',caller.subject,PrincipalKind.HUMAN)
    policy=DataPolicy(platform=ConfirmedPlatform())
    for source in sources:
        if not policy.can_access(principal,DataResource('trino',source),DataAction.QUERY_EXECUTE).allowed:
            raise ConnectionFailure('Helios rejected the platform authorization decision.')
