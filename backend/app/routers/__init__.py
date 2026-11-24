"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import chains
from app.routers import revalidation
from app.routers import resource

# 固定路径路由（chains / revalidation）必须排在通用 /api/{module} 之前注册。
ROUTERS = [chains, revalidation, resource]
