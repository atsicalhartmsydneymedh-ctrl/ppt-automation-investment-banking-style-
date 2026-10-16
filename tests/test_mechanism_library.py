import unittest

from src.mechanism_library import (
    get_mechanism,
    load_layout_variants,
    load_mechanism_registry,
    rank_mechanisms_for_structure,
    select_layout_variant,
    select_mechanism,
    select_mechanism_for_structure,
)


class MechanismLibraryTests(unittest.TestCase):
    def test_registry_loads_all_machine_executable_mechanisms(self):
        mechanisms = load_mechanism_registry()
        self.assertGreaterEqual(len(mechanisms), 70)

    def test_rank4_a_level_variants_are_complete_and_linked(self):
        variants = load_layout_variants()
        self.assertEqual(len(variants), 41)
        self.assertEqual(len({item["id"] for item in variants}), 41)
        mechanism_ids = {item["id"] for item in load_mechanism_registry()}
        self.assertTrue(all(item["parent_mechanism"] in mechanism_ids for item in variants))
        references = [item["source"] for item in variants]
        self.assertTrue(all(set(source) == {"reference_id"} for source in references))
        self.assertEqual(len({source["reference_id"] for source in references}), 41)

    def test_variant_selector_uses_evidence_requirements(self):
        structure = {
            "groups": [
                {"relation": "formula", "item_count": 3},
                {"relation": "evidence_set", "item_count": 4},
            ],
            "requirements": ["formula_operators", "numeric_series"],
        }
        selected = select_layout_variant("R1-L05", structure)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["id"], "R4-S19")

    def test_rank4_variants_route_by_relationship_shape(self):
        cases = [
            (
                "R1-L19",
                {
                    "groups": [
                        {"relation": "parallel_distinct", "item_count": 2},
                        {"relation": "single_anchor", "item_count": 1},
                        {"relation": "foundation_layers", "item_count": 3},
                    ],
                    "requirements": [],
                },
                "R4-S29",
            ),
            (
                "R3-L09",
                {
                    "groups": [
                        {"relation": "feedback_loop", "item_count": 6},
                        {"relation": "containment", "item_count": 6},
                        {"relation": "single_anchor", "item_count": 1},
                    ],
                    "requirements": ["feedback_edges"],
                },
                "R4-S38",
            ),
            (
                "R1-L15",
                {
                    "groups": [
                        {"relation": "parallel_equal", "item_count": 3},
                        {"relation": "uncertainty_range", "item_count": 3},
                        {"relation": "shared_metrics_comparison", "item_count": 3},
                    ],
                    "requirements": ["numeric_series", "range_bounds"],
                },
                "R4-S41",
            ),
        ]
        for mechanism_id, structure, expected in cases:
            with self.subTest(expected=expected):
                selected = select_layout_variant(mechanism_id, structure)
                self.assertIsNotNone(selected)
                self.assertEqual(selected["id"], expected)

    def test_rank4_new_relationships_route_structurally(self):
        cases = [
            (
                {
                    "between_groups": {"relation": "shared_thesis", "mapping": "none"},
                    "groups": [
                        {"id": "map", "position": "any", "relation": "geographic_distribution", "item_count": 8, "order": "none"},
                        {"id": "metrics", "position": "bottom", "relation": "evidence_set", "item_count": 5, "order": "none"},
                    ],
                    "requirements": ["geography"],
                    "forbids": [],
                },
                "R4-L01",
            ),
            (
                {
                    "between_groups": {"relation": "source_to_result", "mapping": "optional"},
                    "groups": [
                        {"id": "source", "position": "left", "relation": "parallel_distinct", "item_count": 3, "order": "none"},
                        {"id": "result", "position": "right", "relation": "parallel_distinct", "item_count": 4, "order": "none"},
                    ],
                    "requirements": [],
                    "forbids": [],
                },
                "R4-L02",
            ),
        ]
        for structure, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(select_mechanism_for_structure(structure)["id"], expected)

    def test_exact_relation_routes_to_expected_execution_card(self):
        selection = select_mechanism("multiple_reasons -> shared_claim, each_reason -> compact_evidence")
        self.assertEqual(selection["id"], "R1-L14")
        self.assertIn("因素", selection["layout_dna"])
        self.assertIn("证据", selection["qa_specific"])
        self.assertTrue(selection["slots"])
        self.assertTrue(selection["source"])
        self.assertEqual(selection["candidate_matches"][0]["id"], "R1-L14")

    def test_all_registered_cards_have_v3_machine_contracts(self):
        for item in load_mechanism_registry():
            mechanism = get_mechanism(item["id"])
            self.assertIsNotNone(mechanism, item["id"])
            self.assertEqual(mechanism["card_contract"]["schema_version"], "3.0", item["id"])
            self.assertEqual(mechanism["card_contract"]["layout_contract"]["sizing"], "adaptive", item["id"])

    def test_structure_matching_selects_parallel_items_plus_tower(self):
        structure = {
            "sizing": "adaptive",
            "between_groups": {"relation": "juxtaposed_peer", "mapping": "none"},
            "groups": [
                {"id": "g1", "position": "left", "relation": "parallel_equal", "item_count": 5, "order": "none"},
                {"id": "g2", "position": "right", "relation": "progressive", "item_count": 4, "order": "required"},
            ],
            "requirements": [],
            "forbids": ["explicit_mapping"],
        }
        selection = select_mechanism_for_structure(structure)
        self.assertEqual(selection["id"], "R2-L13")
        self.assertEqual(selection["match_tier"], "A")
        self.assertNotIn("weight_ratio", selection["card_contract"]["match_signature"])

    def test_hard_gate_rejects_event_window_card_without_dated_events(self):
        structure = {
            "sizing": "adaptive",
            "between_groups": {"relation": "single_group", "mapping": "none"},
            "groups": [
                {"id": "g1", "position": "any", "relation": "time_series", "item_count": 5, "order": "required"}
            ],
            "requirements": ["time_axis", "numeric_series"],
            "forbids": [],
        }
        passed, rejected = rank_mechanisms_for_structure(structure, limit=6, include_rejected=True)
        self.assertNotIn("R2-L14", {item["id"] for item in passed})
        event_card = next(item for item in rejected if item["id"] == "R2-L14")
        self.assertTrue(any("dated_events" in reason for reason in event_card["rejection_reasons"]))

    def test_representative_relationship_families_route_structurally(self):
        cases = [
            ("matrix", 8, "required", ["precise_matrix"], "R2-L15"),
            ("temporal_sequence", 5, "required", ["time_axis", "dated_events"], "R2-L11"),
            ("feedback_loop", 4, "required", ["feedback_edges"], "R1-L26"),
            ("network", 8, "optional", ["geography", "network_flows"], "R2-L09"),
            ("proportional_allocation", 5, "none", ["proportions"], "R3-L17"),
            ("time_series", 5, "required", ["time_axis", "dated_events", "numeric_series"], "R2-L14"),
            ("shared_metrics_comparison", 4, "none", ["shared_scale"], "R1-L15"),
        ]
        for relation, count, order, requirements, expected in cases:
            with self.subTest(relation=relation):
                structure = {
                    "sizing": "adaptive",
                    "between_groups": {"relation": "single_group", "mapping": "none"},
                    "groups": [
                        {"id": "g1", "position": "any", "relation": relation, "item_count": count, "order": order}
                    ],
                    "requirements": requirements,
                    "forbids": [],
                }
                self.assertEqual(select_mechanism_for_structure(structure)["id"], expected)


if __name__ == "__main__":
    unittest.main()
