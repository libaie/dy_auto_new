import subprocess
import sys
from pathlib import Path

from app.db.models import Account as LegacyAccount
from app.db.models import AccountGroup as LegacyAccountGroup
from app.db.models import AccountGroupMember as LegacyAccountGroupMember
from app.db.models import Base
from app.db.models import ChainInstance as LegacyChainInstance
from app.db.models import ChainTemplate as LegacyChainTemplate
from app.db.models import Channel as LegacyChannel
from app.db.models import ChannelItem as LegacyChannelItem


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_account_operations_model_boundary_reexports_account_models():
    from app.db.models.account_operations import (
        Account,
        AccountGroup,
        AccountGroupMember,
        ChainInstance,
        ChainTemplate,
        Channel,
        ChannelItem,
    )

    assert Account is LegacyAccount
    assert AccountGroup is LegacyAccountGroup
    assert AccountGroupMember is LegacyAccountGroupMember
    assert ChainInstance is LegacyChainInstance
    assert ChainTemplate is LegacyChainTemplate
    assert Channel is LegacyChannel
    assert ChannelItem is LegacyChannelItem
    assert Account.metadata is Base.metadata
    assert AccountGroup.metadata is Base.metadata
    assert AccountGroupMember.metadata is Base.metadata
    assert ChainInstance.metadata is Base.metadata
    assert ChainTemplate.metadata is Base.metadata
    assert Channel.metadata is Base.metadata
    assert ChannelItem.metadata is Base.metadata
    assert "accounts" in Base.metadata.tables
    assert "account_groups" in Base.metadata.tables
    assert "account_group_members" in Base.metadata.tables
    assert "chain_instances" in Base.metadata.tables
    assert "chain_templates" in Base.metadata.tables
    assert "channels" in Base.metadata.tables
    assert "channel_items" in Base.metadata.tables


def test_account_operations_model_boundary_imports_in_clean_process():
    code = (
        "import app.db.models as legacy; "
        "from app.db.models.account_operations import Account, AccountGroup, AccountGroupMember, ChainInstance, ChainTemplate, Channel, ChannelItem; "
        "assert legacy.Account is Account; "
        "assert legacy.AccountGroup is AccountGroup; "
        "assert legacy.AccountGroupMember is AccountGroupMember; "
        "assert legacy.ChainInstance is ChainInstance; "
        "assert legacy.ChainTemplate is ChainTemplate; "
        "assert legacy.Channel is Channel; "
        "assert legacy.ChannelItem is ChannelItem; "
        "assert 'accounts' in legacy.Base.metadata.tables; "
        "assert 'account_group_members' in legacy.Base.metadata.tables; "
        "assert 'chain_templates' in legacy.Base.metadata.tables; "
        "assert 'channel_items' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
