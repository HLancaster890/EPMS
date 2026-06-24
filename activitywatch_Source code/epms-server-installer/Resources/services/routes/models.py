from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.0.0"
    uptime_seconds: float = 0
    database: str = "connected"
    redis: str = "connected"


class AgentRegister(BaseModel):
    display_name: str = ""
    hostname: str = ""
    version: str = "1.0.0"
    os: str = "Windows"
    capabilities: Dict[str, bool] = {}


class AgentHeartbeat(BaseModel):
    timestamp: str = ""
    active_window: Dict[str, Any] = {}
    foreground_window: Optional[Dict[str, Any]] = None
    browser_activity: Optional[Dict[str, Any]] = None
    editor_activity: Optional[Dict[str, Any]] = None
    afk_seconds: float = 0
    is_afk: bool = False
    system: Dict[str, Any] = {}
    processes: Optional[List[Dict[str, Any]]] = None


class NotificationRequest(BaseModel):
    type: str = "in_app"
    title: str
    message: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    email: Optional[str] = None
    priority: str = "normal"


class ReportRequest(BaseModel):
    type: str = "activity"
    format: str = "csv"
    agent_ids: Optional[List[str]] = None
    date_from: str = ""
    date_to: str = ""
    organization_id: Optional[str] = None
    user_emails: Optional[List[str]] = None
    report_title: str = "Activity Report"


class ProductivityRuleRequest(BaseModel):
    pattern: str = Field(..., description="App/window title pattern (glob or regex)")
    category: str = Field(..., pattern="^(productive|neutral|distracting)$")
    rule_type: str = Field(default="glob", pattern="^(glob|regex|exact)$")
    description: str = ""


class ProductivityRuleResponse(BaseModel):
    id: str
    organization_id: str
    pattern: str
    category: str
    rule_type: str
    description: str
    is_active: bool
    created_at: str


class BrowserEvent(BaseModel):
    timestamp: str = ""
    browser_name: str = ""
    domain: str = ""
    url: str = ""
    page_title: str = ""
    category: str = "uncategorized"
    is_productive: bool = True
    is_active: bool = True


class EditorEvent(BaseModel):
    timestamp: str = ""
    editor_name: str = ""
    project_name: str = ""
    file_name: str = ""
    file_extension: str = ""
    language: str = ""
    is_focused: bool = True


class BatchEvents(BaseModel):
    events: List[Dict[str, Any]] = []
    timestamp: str = ""
    agent_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 1:
            raise ValueError("Password is required")
        return v


class ADLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 1:
            raise ValueError("Password is required")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900
    user: Optional[Dict[str, Any]] = None


class SystemInventoryResponse(BaseModel):
    agent_id: str = ""
    hostname: str = ""
    os: str = ""
    os_version: str = ""
    os_build: str = ""
    cpu_model: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_architecture: str = ""
    total_ram_gb: float = 0
    total_disk_gb: float = 0
    used_disk_gb: float = 0
    free_disk_gb: float = 0
    ip_address: str = ""
    mac_address: str = ""
    last_boot: str = ""
    last_inventory_update: str = ""
    installed_software: List[Dict[str, Any]] = []
    network_interfaces: List[Dict[str, Any]] = []
    running_services: List[Dict[str, Any]] = []


class InventorySummaryResponse(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    offline_devices: int = 0
    idle_devices: int = 0
    os_breakdown: List[Dict[str, Any]] = []
    total_cpu_cores: int = 0
    total_ram_gb: float = 0
    total_disk_gb: float = 0
    avg_cpu_cores: float = 0
    avg_ram_gb: float = 0
    avg_disk_gb: float = 0
    software_count: int = 0
    service_count: int = 0
    unpatched_count: int = 0


class HealthDeviceResponse(BaseModel):
    agent_id: str = ""
    hostname: str = ""
    status: str = "healthy"
    health_score: float = 100
    cpu_usage_percent: float = 0
    memory_usage_percent: float = 0
    disk_usage_percent: float = 0
    uptime_seconds: int = 0
    last_heartbeat: str = ""
    active_alerts: int = 0
    process_count: int = 0
    thread_count: int = 0
    handle_count: int = 0
    performance_index: float = 1.0
    stability_score: float = 1.0


class HealthAnomalyItem(BaseModel):
    id: str = ""
    agent_id: str = ""
    hostname: str = ""
    type: str = "cpu"
    severity: str = "warning"
    message: str = ""
    value: float = 0
    threshold: float = 0
    detected_at: str = ""
    acknowledged: bool = False


class ExecutiveSummaryResponse(BaseModel):
    total_devices: int = 0
    online_devices: int = 0
    offline_devices: int = 0
    idle_devices: int = 0
    total_users: int = 0
    active_users_today: int = 0
    total_teams: int = 0
    total_organizations: int = 0
    overall_health_score: float = 100
    avg_productivity: float = 0
    productivity_trend: str = "stable"
    alerts_active: int = 0
    alerts_critical: int = 0
    total_uptime_hours: float = 0
    avg_uptime_per_device_hours: float = 0
    top_performers: List[Dict[str, Any]] = []
    needs_attention: List[Dict[str, Any]] = []
    weekly_comparison: Dict[str, Any] = {}
    department_breakdown: List[Dict[str, Any]] = []


class EnrollmentTokenRequest(BaseModel):
    organization_id: Optional[str] = None
    description: str = "Enrollment token for agent registration"