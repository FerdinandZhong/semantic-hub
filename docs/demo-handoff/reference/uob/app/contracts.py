from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from .time_scope import TimeRange, ExactTime

class Query(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tab: Literal['nifi', 'observability', 'data']
    question: str = Field(min_length=3, max_length=1500)
    mode: Literal['live', 'sample'] = 'live'
    source: Literal['auto', 'kibana', 'opensearch', 'prometheus'] = 'auto'
    minutes: int = Field(default=60, ge=5, le=1440)
    observability_path: Literal['auto','events','summary','exact']='auto'
    time_range: TimeRange | None=None
    exact_time: ExactTime | None=None

    @model_validator(mode='after')
    def valid_scope(self):
        if self.time_range and self.exact_time:raise ValueError('Select an absolute range or an exact timestamp, not both.')
        if self.tab!='observability' and (self.time_range or self.exact_time or self.observability_path!='auto'):
            raise ValueError('Absolute log/metric controls apply only to Observability.')
        if (self.observability_path=='exact' or self.exact_time) and self.source=='prometheus':raise ValueError('Exact log lookup requires a log source.')
        if self.exact_time and self.observability_path in {'events','summary'}:raise ValueError('Exact timestamp conflicts with the selected path.')
        return self

class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: Literal['nifi_status', 'nifi_bulletins', 'nifi_processors', 'logs', 'metrics', 'semantic_describe', 'semantic_query']
    search: str = Field(default='', max_length=300)
    metric: Literal['up', 'cpu', 'memory', 'scrape_duration'] = 'up'
    semantic: dict = Field(default_factory=dict)
    log_intent: Literal['events','summary','exact']='events'
    group_by: Literal['error_code','severity','service']='error_code'
    follow_up_metric: Literal['up','cpu','memory','scrape_duration'] | None=None
