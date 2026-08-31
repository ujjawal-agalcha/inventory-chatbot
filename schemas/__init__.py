from .auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    AuthTokenResponse,
)
from .conversation import (
    CreateConversationRequest,
    UpdateConversationRequest,
    ConversationResponse,
    MessageResponse,
    ConversationDetailResponse,
)
from .inventory import (
    ReorderRequestBody,
    StockUpdateBody,
    ProductUpdateBody,
    ProductResponse,
)
from .chat import (
    ChatMessagePayload,
    ChatTokenEvent,
    ChatDoneEvent,
    ChatErrorEvent,
)
from .dashboard import (
    InventoryStatsResponse,
    CategorySummary,
    SupplierSummary,
    MonthlyExpenseSummary,
    DashboardAnalyticsResponse,
)
