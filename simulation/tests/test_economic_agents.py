import pytest
from app.models.schemas import ScenarioConfig
from simulation.economic_agents import (
    MesaDeliveryAgent,
    MesaStallOwner,
    MesaStoreManager,
    MesaStoreStaff,
)
from simulation.engine import UrbanModel


@pytest.fixture
def base_config():
    return ScenarioConfig(
        name="test_scenario",
        city="delhi",
        population=100,
        seed=42,
        use_real_data=False,
    )


def test_economic_agents_spawn(base_config):
    """Test that economic agents are spawned in correct proportions."""
    model = UrbanModel(base_config)

    stalls = [a for a in model.schedule.agents if isinstance(a, MesaStallOwner)]
    managers = [a for a in model.schedule.agents if isinstance(a, MesaStoreManager)]
    staff = [a for a in model.schedule.agents if isinstance(a, MesaStoreStaff)]
    delivery = [a for a in model.schedule.agents if isinstance(a, MesaDeliveryAgent)]

    assert len(stalls) == 5  # 5% of 100
    assert len(managers) == 1  # 1% of 100
    assert len(staff) == 2  # 2% of 100
    assert len(delivery) == 2  # 2% of 100


def test_stall_owner_steps(base_config):
    """Test that StallOwner processes a day, decays inventory, and earns money."""
    model = UrbanModel(base_config)

    stall = next(a for a in model.schedule.agents if isinstance(a, MesaStallOwner))

    # Set time to 10:00 AM
    model.sim_time_minutes = 10 * 60

    # Force state to prevent random failures
    stall._has_begun_day = True
    stall.is_disrupted_today = False

    initial_inv = stall.inventory

    # Step a few times
    for _ in range(3):
        stall.step()
        model.sim_time_minutes += 5

    assert stall.inventory < initial_inv


def test_delivery_agent_rain_surge(base_config):
    """Test dynamic rain pricing for delivery agents."""
    model = UrbanModel(base_config)

    delivery = next(
        a for a in model.schedule.agents if isinstance(a, MesaDeliveryAgent)
    )

    # Base fee
    base_fee = delivery.get_delivery_fee(10.0, 0.0)
    assert base_fee == 10.0

    # Surge fee
    surge_fee = delivery.get_delivery_fee(10.0, 0.8)
    assert surge_fee > 10.0
    assert surge_fee == 10.0 * (1.0 + 1.5 * 0.8)


def test_dynamic_restock_time(base_config):
    """Test that restocking uses dynamic travel times."""
    model = UrbanModel(base_config)
    stall = next(a for a in model.schedule.agents if isinstance(a, MesaStallOwner))

    # Force low inventory to trigger restock
    stall.inventory = 0.0
    stall._has_begun_day = True

    # Set time to midday
    model.sim_time_minutes = 12 * 60

    stall.step()

    assert stall.inventory > 0.0
    assert stall.cash_balance < 1000.0  # Spent money on restock


def test_enforcement_officer_evicts_stall(base_config):
    """Test that Enforcement Officer fines and evicts a roadside stall at the same node."""
    from simulation.economic_agents import MesaEnforcementOfficer
    model = UrbanModel(base_config)

    stall = next(a for a in model.schedule.agents if isinstance(a, MesaStallOwner))
    target_node = stall.current_location

    officer = MesaEnforcementOfficer(
        model=model,
        officer_id=9999,
        patrol_nodes=[str(target_node)]
    )

    initial_cash = stall.cash_balance
    initial_frustration = stall.retail_memory.frustration

    # Step officer at the same location as stall
    officer.step()

    # Stall should be fined ₹100
    assert stall.cash_balance == initial_cash - 100.0
    # Stall frustration should increase by 2.0 (eviction)
    assert stall.retail_memory.frustration > initial_frustration
    # Stall should have relocated to a candidate node
    assert stall.current_location != target_node


def test_drainage_worker_mitigates_flooding(base_config):
    """Test that Drainage Worker adds its node to network's drained_nodes set under rain."""
    from simulation.economic_agents import MesaDrainageWorker
    model = UrbanModel(base_config)

    worker = MesaDrainageWorker(
        model=model,
        worker_id=8888,
        base_node="node_0_0"
    )

    # Set rain intensity
    model.network.weather_rain_intensity = 0.5

    # Initially, drained_nodes is empty
    assert "node_0_0" not in model.network.drained_nodes

    # Step worker
    worker.step()

    # Now, node_0_0 should be registered as drained
    assert "node_0_0" in model.network.drained_nodes


def test_traffic_police_boosts_capacity(base_config):
    """Test that Traffic Police adds its node to network's traffic_police_nodes set."""
    from simulation.economic_agents import MesaTrafficPolice
    model = UrbanModel(base_config)

    police = MesaTrafficPolice(
        model=model,
        police_id=7777,
        intersection_node="node_1_1"
    )

    # Initially, traffic_police_nodes is empty
    assert "node_1_1" not in model.network.traffic_police_nodes

    # Step police
    police.step()

    # Now, node_1_1 should be registered as policed
    assert "node_1_1" in model.network.traffic_police_nodes
