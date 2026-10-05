# ফাইল: backend/apps/hr/urls.py
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet, PositionViewSet, EmployeeViewSet,
    PayheadViewSet, PayrollViewSet, AttendanceViewSet,
    ResignRuleViewSet, ResignationViewSet, RejoinViewSet,
)

router = DefaultRouter()
router.register(r'departments',  DepartmentViewSet,  basename='department')
router.register(r'positions',    PositionViewSet,    basename='position')
router.register(r'employees',    EmployeeViewSet,    basename='employee')
router.register(r'payheads',     PayheadViewSet,     basename='payhead')
router.register(r'payrolls',     PayrollViewSet,     basename='payroll')
router.register(r'attendance',   AttendanceViewSet,  basename='attendance')
router.register(r'resign-rules', ResignRuleViewSet,  basename='resign-rule')
router.register(r'resignations', ResignationViewSet, basename='resignation')
router.register(r'rejoins',      RejoinViewSet,      basename='rejoin')

urlpatterns = router.urls
