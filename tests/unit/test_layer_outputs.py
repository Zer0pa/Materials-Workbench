"""Unit tests for per-layer output schemas (PRD §Layer Contracts)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from zer0pa_materials_workbench.envelope import (
    LAYER_OUTPUT_REGISTRY,
    IonicTransportOutput,
    L1DftOutput,
    L1QuantumVqeOutput,
    L2MlipOutput,
    L3CalphadOutput,
    L4PhaseFieldOutput,
    L5ContinuumOutput,
    L6GenerativeOutput,
    L7CampaignOutput,
    L15PhononOutput,
    Phase0ExtractedProperty,
    Phase0Output,
    Phase0PropertyGrounding,
    sha256_of,
    validate_layer_output,
)
from zer0pa_materials_workbench.envelope.layer_outputs import (
    IonicArrhenius,
    L2ModelPrediction,
    L5TensorRecord,
    L6DedupResult,
)

# ----------------------------------------------------------------------------
# Registry coverage
# ----------------------------------------------------------------------------


def test_registry_contains_all_layer_slots():
    expected = {
        "phase0", "L1", "L1.5", "ionic", "quantum",
        "L2", "L3", "L4", "L5", "L6", "L7",
    }
    assert set(LAYER_OUTPUT_REGISTRY.keys()) == expected


def test_validate_layer_output_unknown_layer_raises():
    with pytest.raises(KeyError):
        validate_layer_output("L42", {})


def test_validate_layer_output_phase0_smoke():
    obj = validate_layer_output(
        "phase0",
        {"extracted_properties": [], "units_normalised": True, "contradictions_blocking": []},
    )
    assert isinstance(obj, Phase0Output)


# ----------------------------------------------------------------------------
# Phase 0
# ----------------------------------------------------------------------------


def test_phase0_grounding_required_pass():
    p = Phase0Output(
        extracted_properties=[
            Phase0ExtractedProperty(
                property_name="ionic_conductivity",
                value=1.0e-3,
                unit="S/cm",
                grounding=Phase0PropertyGrounding(doi="10.1234/x", page=5, table="Table 1"),
            )
        ],
        units_normalised=True,
        contradictions_blocking=[],
    )
    items = p.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["phase0.grounding_required"] == "pass"
    assert statuses["phase0.units_normalised"] == "pass"
    assert statuses["phase0.contradictions_resolved"] == "pass"


def test_phase0_grounding_missing_doi_rejected_at_schema():
    """Schema-level requirement: grounding.doi non-empty."""
    with pytest.raises(ValidationError):
        Phase0ExtractedProperty(
            property_name="ionic_conductivity",
            value=1.0e-3,
            unit="S/cm",
            grounding=Phase0PropertyGrounding(doi=""),
        )


def test_phase0_contradictions_blocking_fails():
    p = Phase0Output(contradictions_blocking=["sigma_300K"])
    items = p.falsifier_items()
    f = next(it for it in items if it.name == "phase0.contradictions_resolved")
    assert f.status == "fail"


# ----------------------------------------------------------------------------
# L6 generative
# ----------------------------------------------------------------------------


def test_l6_generative_pass_when_unique_and_valid():
    o = L6GenerativeOutput(
        candidate_uri="file:///tmp/cand.cif",
        structure_hash=sha256_of({"a": 1}),
        novelty_status="novel",
        dedup_results=[L6DedupResult(source="MP", matched=False)],
        cif_valid=True,
        charge_neutral=True,
        minimum_distance_ok=True,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l6.cif_valid"] == "pass"
    assert statuses["l6.dedup_unique"] == "pass"
    assert statuses["l6.novelty_resolved"] == "pass"


def test_l6_generative_fails_on_duplicate():
    o = L6GenerativeOutput(
        candidate_uri="file:///tmp/dup.cif",
        structure_hash=sha256_of({"x": 9}),
        novelty_status="duplicate",
        dedup_results=[
            L6DedupResult(source="MP", matched=True, matched_id="mp-1234"),
        ],
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l6.dedup_unique"] == "fail"


def test_l6_pending_novelty_blocks():
    o = L6GenerativeOutput(
        candidate_uri="file:///tmp/x.cif",
        structure_hash=sha256_of({"y": 1}),
        novelty_status="pending",
    )
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l6.novelty_resolved")
    assert f.status == "blocked"


def test_l6_structure_hash_format_validated():
    with pytest.raises(ValidationError):
        L6GenerativeOutput(
            candidate_uri="file:///x", structure_hash="not-a-sha", novelty_status="novel"
        )


# ----------------------------------------------------------------------------
# L1 DFT
# ----------------------------------------------------------------------------


def test_l1_dft_publication_grade_pass():
    o = L1DftOutput(
        code="QE",
        functional="PBE",
        total_energy_eV=-15.4,
        force_rmse_eV_per_Ang=0.01,
        kpoint_mesh=[6, 6, 6],
        convergence_delta_meV_per_atom=2.0,
        publication_grade=True,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.publication_convergence_delta"] == "pass"
    assert statuses["l1.screening_convergence_delta"] == "pass"


def test_l1_dft_publication_grade_fails_above_5():
    o = L1DftOutput(
        code="QE",
        functional="PBE",
        total_energy_eV=-15.4,
        force_rmse_eV_per_Ang=0.01,
        kpoint_mesh=[6, 6, 6],
        convergence_delta_meV_per_atom=12.0,
        publication_grade=True,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.publication_convergence_delta"] == "fail"
    assert statuses["l1.screening_convergence_delta"] == "pass"


def test_l1_dft_screening_fails_above_50():
    o = L1DftOutput(
        code="QE",
        functional="PBE",
        total_energy_eV=-15.4,
        force_rmse_eV_per_Ang=0.01,
        kpoint_mesh=[6, 6, 6],
        convergence_delta_meV_per_atom=72.0,
        publication_grade=False,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.screening_convergence_delta"] == "fail"


def test_l1_dft_kpoint_mesh_length_enforced():
    with pytest.raises(ValidationError):
        L1DftOutput(
            code="QE",
            functional="PBE",
            total_energy_eV=-1.0,
            force_rmse_eV_per_Ang=0.0,
            kpoint_mesh=[1, 2],
        )


# ----------------------------------------------------------------------------
# L1 quantum VQE
# ----------------------------------------------------------------------------


def test_l1_vqe_h2_pass():
    o = L1QuantumVqeOutput(
        system="H2",
        ansatz="UCCSD",
        qubits=4,
        optimizer="COBYLA",
        ground_state_energy_Ha=-1.137,
        classical_reference_Ha=-1.13728,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.h2_vqe_vs_fci"] == "pass"


def test_l1_vqe_h2_fail_above_threshold():
    o = L1QuantumVqeOutput(
        system="H2",
        ansatz="UCCSD",
        qubits=4,
        optimizer="COBYLA",
        ground_state_energy_Ha=-1.0,
        classical_reference_Ha=-1.13728,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.h2_vqe_vs_fci"] == "fail"


def test_l1_vqe_lih_pass():
    o = L1QuantumVqeOutput(
        system="LiH",
        ansatz="UCCSD",
        qubits=8,
        optimizer="L-BFGS-B",
        ground_state_energy_Ha=-7.882,
        classical_reference_Ha=-7.880,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l1.lih_vqe_vs_fci"] == "pass"


def test_l1_vqe_lih_fail():
    o = L1QuantumVqeOutput(
        system="LiH",
        ansatz="HEA(p=2)",
        qubits=8,
        optimizer="SPSA",
        ground_state_energy_Ha=-7.7,
        classical_reference_Ha=-7.880,
    )
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l1.lih_vqe_vs_fci")
    assert f.status == "fail"


# ----------------------------------------------------------------------------
# Ionic transport
# ----------------------------------------------------------------------------


def test_ionic_transport_full_pass():
    o = IonicTransportOutput(
        migration_barrier_eV=0.28,
        msd_A2=15.2,
        diffusion_coefficient_cm2_per_s=2.0e-6,
        nernst_einstein_conductivity_S_per_cm=2.0e-3,
        arrhenius=IonicArrhenius(activation_energy_eV=0.30, activation_energy_uncertainty_eV=0.02),
        electrochemical_window_V_vs_LiLi=(0.5, 4.5),
        interface_stability="li_metal_unstable_coating_required",
        defect_disorder_assumptions=["dilute Li-vacancy"],
        confidence=0.6,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["ionic.activation_barrier_target"] == "pass"
    assert statuses["ionic.activation_barrier_stretch"] == "pass"
    assert statuses["ionic.rt_conductivity_target"] == "pass"
    assert statuses["ionic.oxidative_stability"] == "pass"


def test_ionic_transport_blocked_when_missing_measurements():
    o = IonicTransportOutput()
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["ionic.activation_barrier_target"] == "blocked"
    assert statuses["ionic.rt_conductivity_target"] == "blocked"
    assert statuses["ionic.oxidative_stability"] == "blocked"


def test_ionic_transport_oxidative_stability_below_threshold_fails():
    o = IonicTransportOutput(
        migration_barrier_eV=0.40,
        nernst_einstein_conductivity_S_per_cm=5e-4,
        electrochemical_window_V_vs_LiLi=(1.0, 3.5),
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["ionic.activation_barrier_target"] == "fail"
    assert statuses["ionic.rt_conductivity_target"] == "fail"
    assert statuses["ionic.oxidative_stability"] == "fail"


# ----------------------------------------------------------------------------
# L1.5 phonon
# ----------------------------------------------------------------------------


def test_l15_phonon_full_pass():
    o = L15PhononOutput(
        imaginary_mode_max_THz=0.1,
        mlip_vs_dft_force_rmse_eV_per_Ang=0.02,
        qmesh_convergence_pct=4.0,
        seebeck_uV_per_K=200.0,
        electrical_conductivity_S_per_cm=1.5,
        thermal_conductivity_W_per_mK=2.0,
        zt=1.2,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l15.imaginary_mode_threshold"] == "pass"
    assert statuses["l15.mlip_vs_dft_force_rmse"] == "pass"
    assert statuses["l15.phono3py_qmesh_convergence"] == "pass"


def test_l15_phonon_imaginary_mode_fail():
    o = L15PhononOutput(imaginary_mode_max_THz=0.5)
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l15.imaginary_mode_threshold")
    assert f.status == "fail"


def test_l15_phonon_mlip_force_rmse_escalates():
    o = L15PhononOutput(
        imaginary_mode_max_THz=0.0, mlip_vs_dft_force_rmse_eV_per_Ang=0.08
    )
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l15.mlip_vs_dft_force_rmse")
    assert f.status == "fail"


# ----------------------------------------------------------------------------
# L2 MLIP
# ----------------------------------------------------------------------------


def test_l2_mlip_promote_pass():
    o = L2MlipOutput(
        predictions=[
            L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-2.4, force_rmse_eV_per_Ang=0.05),
            L2ModelPrediction(model="MACE-MPA-0", energy_eV_per_atom=-2.41, force_rmse_eV_per_Ang=0.06),
        ],
        energy_disagreement_meV_per_atom=10.0,
        force_rmse_disagreement_eV_per_Ang=0.05,
        routing_decision="promote",
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l2.energy_disagreement_promote"] == "pass"
    assert statuses["l2.force_rmse_promote"] == "pass"
    assert statuses["l2.energy_disagreement_hard_reject"] == "pass"


def test_l2_mlip_queue_dft():
    o = L2MlipOutput(
        predictions=[
            L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-2.0, force_rmse_eV_per_Ang=0.05),
            L2ModelPrediction(model="MACE-MPA-0", energy_eV_per_atom=-2.04, force_rmse_eV_per_Ang=0.20),
        ],
        energy_disagreement_meV_per_atom=40.0,
        force_rmse_disagreement_eV_per_Ang=0.20,
        routing_decision="queue_dft",
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l2.energy_disagreement_promote"] == "fail"
    assert statuses["l2.force_rmse_promote"] == "fail"
    # still below hard-reject thresholds
    assert statuses["l2.energy_disagreement_hard_reject"] == "pass"
    assert statuses["l2.force_rmse_hard_reject"] == "pass"


def test_l2_mlip_hard_reject():
    o = L2MlipOutput(
        predictions=[
            L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-2.0, force_rmse_eV_per_Ang=0.05),
            L2ModelPrediction(model="MACE-MPA-0", energy_eV_per_atom=-2.10, force_rmse_eV_per_Ang=0.50),
        ],
        energy_disagreement_meV_per_atom=100.0,
        force_rmse_disagreement_eV_per_Ang=0.5,
        routing_decision="hard_reject",
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l2.energy_disagreement_hard_reject"] == "fail"
    assert statuses["l2.force_rmse_hard_reject"] == "fail"


def test_l2_mlip_distinct_models_required():
    """When two predictions are present they MUST be distinct models."""
    with pytest.raises(ValidationError):
        L2MlipOutput(
            predictions=[
                L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-2.0, force_rmse_eV_per_Ang=0.05),
                L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-2.04, force_rmse_eV_per_Ang=0.20),
            ],
            energy_disagreement_meV_per_atom=40.0,
            force_rmse_disagreement_eV_per_Ang=0.20,
            routing_decision="queue_dft",
        )


# ----------------------------------------------------------------------------
# L3 CALPHAD
# ----------------------------------------------------------------------------


def test_l3_calphad_full_pass():
    o = L3CalphadOutput(
        tdb_ref="urn:zer0pa:tdb:open:cu-mg:0.1",
        equilibrium_phases=["FCC", "LIQUID"],
        phase_fraction_posterior={"FCC": 0.7, "LIQUID": 0.3},
        espei_diagnostics={"r_hat": 1.02, "ess": 1500},
        fixture_phase_boundary_drift_K=10.0,
        phase_set_jaccard_distance=0.10,
        phase_fraction_js_divergence=0.05,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l3.fixture_boundary_drift"] == "pass"
    assert statuses["l3.phase_set_jaccard"] == "pass"
    assert statuses["l3.phase_fraction_js_divergence"] == "pass"
    assert statuses["l3.espei_diagnostics_recorded"] == "pass"


def test_l3_calphad_jaccard_escalates():
    o = L3CalphadOutput(
        tdb_ref="urn:test", phase_set_jaccard_distance=0.50,
        espei_diagnostics={"r_hat": 1.0},
    )
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l3.phase_set_jaccard")
    assert f.status == "fail"


def test_l3_calphad_diagnostics_blocked_when_empty():
    o = L3CalphadOutput(tdb_ref="urn:test", espei_diagnostics={})
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l3.espei_diagnostics_recorded")
    assert f.status == "blocked"


# ----------------------------------------------------------------------------
# L4 phase field / kMC
# ----------------------------------------------------------------------------


def test_l4_phase_field_full_pass():
    o = L4PhaseFieldOutput(
        cahn_hilliard_mass_drift=1e-4,
        allen_cahn_bounds_violation=1e-5,
        spparks_potts_energy_monotonic=True,
        microstructure_trajectory_uri="file:///tmp/traj.h5",
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l4.cahn_hilliard_mass_drift"] == "pass"
    assert statuses["l4.allen_cahn_bounds_violation"] == "pass"
    assert statuses["l4.spparks_potts_energy_monotonic"] == "pass"


def test_l4_mass_drift_fail():
    o = L4PhaseFieldOutput(cahn_hilliard_mass_drift=1e-2)
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l4.cahn_hilliard_mass_drift")
    assert f.status == "fail"


def test_l4_potts_blocked_when_unset():
    o = L4PhaseFieldOutput()
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l4.spparks_potts_energy_monotonic")
    assert f.status == "blocked"


# ----------------------------------------------------------------------------
# L5 continuum
# ----------------------------------------------------------------------------


def test_l5_continuum_full_pass():
    o = L5ContinuumOutput(
        tensors=[
            L5TensorRecord(name="stiffness", spd=True, eigvals_min=1.0),
            L5TensorRecord(name="conductivity", spd=True, eigvals_min=0.1),
        ],
        analytic_heat_slab_error=1e-7,
        elastic_patch_residual=1e-9,
        fenicsx_vs_dealii_strain_energy_disagreement_pct=1.0,
        openfoam_poiseuille_error_pct=2.0,
        cfd_mass_balance_error=1e-5,
        cfd_heat_balance_error=1e-5,
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l5.tensors_spd"] == "pass"
    assert statuses["l5.analytic_heat_slab_error"] == "pass"
    assert statuses["l5.elastic_patch_residual"] == "pass"
    assert statuses["l5.fenicsx_vs_dealii"] == "pass"
    assert statuses["l5.openfoam_poiseuille_error"] == "pass"
    assert statuses["l5.cfd_mass_balance"] == "pass"
    assert statuses["l5.cfd_heat_balance"] == "pass"


def test_l5_non_spd_fails():
    o = L5ContinuumOutput(
        tensors=[L5TensorRecord(name="stiffness", spd=False, eigvals_min=-0.1)]
    )
    items = o.falsifier_items()
    f = next(it for it in items if it.name == "l5.tensors_spd")
    assert f.status == "fail"


# ----------------------------------------------------------------------------
# L7 campaign
# ----------------------------------------------------------------------------


def test_l7_campaign_pass():
    o = L7CampaignOutput(
        candidate_id="candidate:abc",
        acquisition="qMultiFidelityKnowledgeGradient",
        promotion_decision="promote",
        audit_provenance_ref="audit:campaign-001",
        gate_verdict="pass",
    )
    items = o.falsifier_items()
    statuses = {it.name: it.status for it in items}
    assert statuses["l7.audit_provenance_attached"] == "pass"
    assert statuses["l7.gate_verdict"] == "pass"


def test_l7_candidate_id_format_enforced():
    with pytest.raises(ValidationError):
        L7CampaignOutput(
            candidate_id="not-a-urn",
            acquisition="qLogExpectedImprovement",
            promotion_decision="hold",
            audit_provenance_ref="audit:x",
            gate_verdict="pass",
        )


# ----------------------------------------------------------------------------
# Every layer-output model produces falsifier_items
# ----------------------------------------------------------------------------


def test_every_layer_output_has_falsifier_items_method():
    """Smoke-test that every layer-output class has a callable falsifier_items()
    method that returns a list (possibly empty)."""
    minimal_args: dict[str, dict] = {
        "phase0": dict(),
        "L1": dict(
            code="QE", functional="PBE", total_energy_eV=-1.0,
            force_rmse_eV_per_Ang=0.0, kpoint_mesh=[1, 1, 1],
        ),
        "L1.5": dict(imaginary_mode_max_THz=0.0),
        "ionic": dict(),
        "quantum": dict(
            system="H2", ansatz="UCCSD", qubits=4, optimizer="COBYLA",
            ground_state_energy_Ha=-1.137, classical_reference_Ha=-1.137,
        ),
        "L2": dict(
            predictions=[L2ModelPrediction(model="X", energy_eV_per_atom=-1.0, force_rmse_eV_per_Ang=0.0)],
            energy_disagreement_meV_per_atom=0.0,
            force_rmse_disagreement_eV_per_Ang=0.0,
            routing_decision="promote",
        ),
        "L3": dict(tdb_ref="urn:test"),
        "L4": dict(),
        "L5": dict(),
        "L6": dict(
            candidate_uri="file:///x", structure_hash=sha256_of({"a": 1}),
            novelty_status="novel",
        ),
        "L7": dict(
            candidate_id="candidate:x",
            acquisition="qLogExpectedImprovement",
            promotion_decision="promote",
            audit_provenance_ref="audit:y",
            gate_verdict="pass",
        ),
    }
    for layer, cls in LAYER_OUTPUT_REGISTRY.items():
        instance = cls(**minimal_args[layer])
        items = instance.falsifier_items()
        assert isinstance(items, list)
        for it in items:
            assert it.name
            assert it.status in {"pass", "fail", "blocked", "inconclusive"}
