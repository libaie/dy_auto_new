"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 realtime_events 相关业务规则、状态转换和外部系统边界。
"""

from app.ws_manager import pair_ws_manager


async def broadcast_content_changed():
    """业务函数：处理 broadcast_content_changed 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.broadcast_to_admins({"event": "content_changed"})


async def broadcast_data_changed(entity_type: str, entity_id):
    """业务函数：处理 broadcast_data_changed 对应的业务流程、校验或数据转换。

    入参：entity_type、entity_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    await pair_ws_manager.broadcast_to_admins({
        "event": "data_changed",
        "type": entity_type,
        "id": entity_id,
    })
