# F2-1 Report — Single Source of Parameter Truth

Branch: `packet/f2-1`
Protocol: local commit only; no push.

## Scope outcome

- Read `delivery/packets/F2-1-parameter-truth.md` and ADR 0012 section 2 before editing.
- Deleted executor-side hardcoded defaults from `node_parameter_number`, `node_parameter_integer`, and `node_parameter_text` call sites.
- Changed node-parameter helpers to read only `BoundCatalogNode.resolved_parameters`. A missing read now raises `UndeclaredNodeParameterError` naming capability, node, and parameter.
- Added a static boundary test proving every implementation-level node-parameter read is declared in that capability's catalog entry; shared implementations are checked against every catalog ref they serve.
- Preserved behavior by adding missing catalog defaults to existing declarations for corridor and destination-entry parameters. Round-1 review found these executor defaults were dead behind required declarations; the director ruling below makes the required-to-optional conversion deliberate rather than implicit.
- `state.params` reads are censused only in this packet, per F2-Y fence.

## Director-ratified contract change

Round-1 review rejected the first report because the 22 corridor and destination-entry declarations below changed from `required: true` with no catalog default to optional catalog parameters with defaults, while the report treated the executor default as the only effective default home. The review was correct: at merge-base, the binder rejected omissions, so those executor defaults were dead code.

The director ruling for round 2 is that the optional-with-default contract **stands**. ADR 0012 §2 says the binder materializes catalog defaults into `resolved_parameters` and the executor reads only from there; leaving these values required-with-no-default would keep defaults homeless and force plan authors to restate engine defaults. Therefore the loosening is a deliberate, disclosed contract change, with value domains still guarded by the declared min/max/enum validation.

| Capability | Parameter | Old contract | New contract / authority |
|---|---|---|---|
| `geometric_progressive_corridor` | `max_window_seconds` | required, no catalog default | optional default `4.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `minimum_progression_m` | required, no catalog default | optional default `8.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `minimum_segment_length_m` | required, no catalog default | optional default `8.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `maximum_segment_length_m` | required, no catalog default | optional default `45.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `minimum_clearance_m` | required, no catalog default | optional default `5.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `open_after_frames` | required, no catalog default | optional default `2.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `close_after_frames` | required, no catalog default | optional default `2.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `side_filter` | required, no catalog default | optional default `any`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor` | `minimum_duration_seconds` | required, no catalog default | optional default `0.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `max_window_seconds` | required, no catalog default | optional default `4.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `minimum_progression_m` | required, no catalog default | optional default `8.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `minimum_segment_length_m` | required, no catalog default | optional default `8.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `maximum_segment_length_m` | required, no catalog default | optional default `45.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `minimum_clearance_m` | required, no catalog default | optional default `5.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `open_after_frames` | required, no catalog default | optional default `2.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `close_after_frames` | required, no catalog default | optional default `2.0`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `side_filter` | required, no catalog default | optional default `any`; director ruling under ADR 0012 §2 |
| `geometric_progressive_corridor_from_anchor_set` | `minimum_duration_seconds` | required, no catalog default | optional default `0.0`; director ruling under ADR 0012 §2 |
| `relation_destination_entry` | `destination_entry_horizon_seconds` | required, no catalog default | optional default `6.0`; director ruling under ADR 0012 §2 |
| `relation_destination_entry` | `episode_selection` | required, no catalog default | optional default `entry_first_then_progression`; director ruling under ADR 0012 §2 |
| `relation_destination_entry_classification` | `destination_entry_horizon_seconds` | required, no catalog default | optional default `6.0`; director ruling under ADR 0012 §2 |
| `relation_destination_entry_classification` | `episode_selection` | required, no catalog default | optional default `first_by_duration_clearance`; director ruling under ADR 0012 §2 |

## Census summary

- Capability/helper pairs surveyed: **191**
- Declared in catalog: **191**
- Default agreements after action: **191**
- Existing catalog declarations given today's executor default: **22**
- Remaining default disagreements: **0**
- Shared `state.params` read/passthrough sites censused: **26**
- Total census scope: **191 node-parameter reads + 26 shared `state.params` reads/passthroughs**

## Node-parameter census

| Call site | Parameter | Declared? | Default agreement? | Action taken |
|---|---|---:|---:|---|
| `executor.py:3935` `acceleration` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3936` `acceleration` `text` default `receiver_id` / catalog `receiver_id` | `entity_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3937` `acceleration` `number` default `0.4` / catalog `0.4` | `lookback_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3938` `acceleration` `number` default `0.4` / catalog `0.4` | `minimum_abs_delta_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3939` `acceleration` `number` default `0.75` / catalog `0.75` | `minimum_abs_acceleration_mps2` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3940` `acceleration` `number` default `10.0` / catalog `10.0` | `maximum_player_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3941` `acceleration` `number` default `12.0` / catalog `12.0` | `maximum_abs_acceleration_mps2` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3236` `action_chain` `number` default `5.0` / catalog `5.0` | `maximum_action_gap_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3237` `action_chain` `number` default `2` / catalog `2` | `chain_length` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2941` `action_event_anchor` `text` default `successful_pass` / catalog `successful_pass` | `action_type` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5537` `carry_episode` `number` default `10.0` / catalog `10.0` | `maximum_carry_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5538` `carry_episode` `number` default `3.0` / catalog `3.0` | `minimum_displacement_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5539` `carry_episode` `number` default `2.5` / catalog `2.5` | `control_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5540` `carry_episode` `number` default `1.0` / catalog `1.0` | `nearest_teammate_margin_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5541` `carry_episode` `number` default `10.0` / catalog `10.0` | `maximum_ball_player_speed_delta_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5546` `carry_episode` `number` default `1.0` / catalog `1.0` | `minimum_controlled_frame_ratio` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5547` `carry_episode` `number` default `0.75` / catalog `0.75` | `minimum_comoving_frame_ratio` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5548` `carry_episode` `number` default `0.02` / catalog `0.02` | `maximum_missing_frame_ratio` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3566` `change_across_anchor` `text` default `line_compactness_m` / catalog `line_compactness_m` | `before_value_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3567` `change_across_anchor` `text` default `line_compactness_m` / catalog `line_compactness_m` | `after_value_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3568` `change_across_anchor` `text` default `line_status` / catalog `line_status` | `before_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3569` `change_across_anchor` `text` default `line_status` / catalog `line_status` | `after_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3570` `change_across_anchor` `text` default `PASS` / catalog `PASS` | `required_status_value` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3571` `change_across_anchor` `text` default `increase_at_least` / catalog `increase_at_least` | `change_mode` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3572` `change_across_anchor` `number` default `4.0` / catalog `4.0` | `minimum_change_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3573` `change_across_anchor` `number` default `12.0` / catalog `12.0` | `maximum_before_value_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7283` `controlled_line_break_episode` `number` default `0.5` / catalog `0.5` | `line_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4168` `controlled_pass_episode` `event_type_filter` default `Play_Pass` / catalog `Play_Pass` | `event_type_filter` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4171` `controlled_pass_episode` `number` default `250.0` / catalog `250.0` | `max_release_alignment_ms` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4172` `controlled_pass_episode` `number` default `1.0` / catalog `1.0` | `release_search_before_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4173` `controlled_pass_episode` `number` default `3.0` / catalog `3.0` | `release_search_after_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4174` `controlled_pass_episode` `number` default `4.0` / catalog `4.0` | `reception_search_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4175` `controlled_pass_episode` `number` default `2.5` / catalog `2.5` | `control_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4176` `controlled_pass_episode` `number` default `1.0` / catalog `1.0` | `nearest_teammate_margin_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4177` `controlled_pass_episode` `number` default `0.24` / catalog `0.24` | `minimum_receiver_dwell_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3822` `cover_shadow` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3823` `cover_shadow` `text` default `receiver_id` / catalog `receiver_id` | `target_entity_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3824` `cover_shadow` `text` default `opposition_outfield_to_anchor_team` / catalog `opposition_outfield_to_anchor_team` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3825` `cover_shadow` `number` default `2.0` / catalog `2.0` | `maximum_lane_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3826` `cover_shadow` `number` default `0.05` / catalog `0.05` | `minimum_projection_fraction` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3827` `cover_shadow` `number` default `5.0` / catalog `5.0` | `minimum_lane_length_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3828` `cover_shadow` `integer` default `6` / catalog `6.0` | `minimum_observed_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6392` `defensive_line_model` `number` default `1.0` / catalog `1.0` | `goal_side_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6393` `defensive_line_model` `number` default `2.0` / catalog `2.0` | `line_band_width_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6394` `defensive_line_model` `number` default `4` / catalog `4` | `minimum_line_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6396` `defensive_line_model` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `anchor_frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:9125` `geometric_progressive_corridor` `number` default `4.0` / catalog `4.0` | `max_window_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9126` `geometric_progressive_corridor` `number` default `8.0` / catalog `8.0` | `minimum_progression_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9127` `geometric_progressive_corridor` `number` default `8.0` / catalog `8.0` | `minimum_segment_length_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9128` `geometric_progressive_corridor` `number` default `45.0` / catalog `45.0` | `maximum_segment_length_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9129` `geometric_progressive_corridor` `number` default `5.0` / catalog `5.0` | `minimum_clearance_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9130` `geometric_progressive_corridor` `integer` default `2` / catalog `2.0` | `open_after_frames` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9131` `geometric_progressive_corridor` `integer` default `2` / catalog `2.0` | `close_after_frames` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9139` `geometric_progressive_corridor` `text` default `any` / catalog `any` | `side_filter` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9140` `geometric_progressive_corridor` `number` default `0.0` / catalog `0.0` | `minimum_duration_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9125` `geometric_progressive_corridor_from_anchor_set` `number` default `4.0` / catalog `4.0` | `max_window_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9126` `geometric_progressive_corridor_from_anchor_set` `number` default `8.0` / catalog `8.0` | `minimum_progression_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9127` `geometric_progressive_corridor_from_anchor_set` `number` default `8.0` / catalog `8.0` | `minimum_segment_length_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9128` `geometric_progressive_corridor_from_anchor_set` `number` default `45.0` / catalog `45.0` | `maximum_segment_length_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9129` `geometric_progressive_corridor_from_anchor_set` `number` default `5.0` / catalog `5.0` | `minimum_clearance_m` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9130` `geometric_progressive_corridor_from_anchor_set` `integer` default `2` / catalog `2.0` | `open_after_frames` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9131` `geometric_progressive_corridor_from_anchor_set` `integer` default `2` / catalog `2.0` | `close_after_frames` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9139` `geometric_progressive_corridor_from_anchor_set` `text` default `any` / catalog `any` | `side_filter` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9140` `geometric_progressive_corridor_from_anchor_set` `number` default `0.0` / catalog `0.0` | `minimum_duration_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:5594` `join_episode_sets` `text` default `anchor_id` / catalog `anchor_id` | `left_key_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5595` `join_episode_sets` `text` default `anchor_id` / catalog `anchor_id` | `right_key_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5596` `join_episode_sets` `text` default `none` / catalog `none` | `left_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5597` `join_episode_sets` `text` default `none` / catalog `none` | `right_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5598` `join_episode_sets` `text` default `PASS` / catalog `PASS` | `required_status_value` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5599` `join_episode_sets` `text` default `none` / catalog `none` | `temporal_relation` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5600` `join_episode_sets` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `left_time_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5601` `join_episode_sets` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `right_time_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5602` `join_episode_sets` `number` default `999.0` / catalog `999.0` | `maximum_gap_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5603` `join_episode_sets` `text` default `none` / catalog `none` | `distinct_entity_fields` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:5604` `join_episode_sets` `text` default `none` / catalog `none` | `same_entity_fields` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7389` `lane_occupancy` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7390` `lane_occupancy` `text` default `perspective_outfield` / catalog `perspective_outfield` | `player_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7391` `lane_occupancy` `integer` default `0` / catalog `0` | `required_occupied_lane_count` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8524` `local_number_relation` `text` default `controlled_reception_frame_id` / catalog `controlled_reception_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8525` `local_number_relation` `number` default `10.0` / catalog `10.0` | `radius_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8526` `local_number_relation` `integer` default `1` / catalog `1` | `minimum_difference` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8527` `local_number_relation` `integer` default `0` / catalog `0` | `minimum_perspective_players` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8528` `local_number_relation` `integer` default `99` / catalog `99` | `maximum_defending_players` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3762` `marking` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3763` `marking` `text` default `receiver_id` / catalog `receiver_id` | `target_player_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3764` `marking` `text` default `opposition_outfield_to_anchor_team` / catalog `opposition_outfield_to_anchor_team` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3765` `marking` `number` default `3.0` / catalog `3.0` | `maximum_marking_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3766` `marking` `integer` default `6` / catalog `6.0` | `minimum_observed_marker_candidates` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6446` `multi_line_model` `number` default `1.0` / catalog `1.0` | `goal_side_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6447` `multi_line_model` `number` default `2.0` / catalog `2.0` | `line_band_width_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6448` `multi_line_model` `number` default `3` / catalog `3` | `minimum_line_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6449` `multi_line_model` `number` default `2` / catalog `2` | `target_line_rank` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6450` `multi_line_model` `text` default `physical_release_frame_id` / catalog `physical_release_frame_id` | `anchor_frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3999` `off_ball_run` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4000` `off_ball_run` `text` default `same_team_outfield_as_anchor` / catalog `same_team_outfield_as_anchor` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4001` `off_ball_run` `number` default `1.2` / catalog `1.2` | `lookahead_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4002` `off_ball_run` `number` default `4.0` / catalog `4.0` | `minimum_run_displacement_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4003` `off_ball_run` `number` default `3.0` / catalog `3.0` | `minimum_run_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4004` `off_ball_run` `number` default `5.0` / catalog `5.0` | `minimum_ball_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4005` `off_ball_run` `integer` default `6` / catalog `6.0` | `minimum_observed_candidates` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4006` `off_ball_run` `number` default `0.35` / catalog `0.35` | `maximum_missing_candidate_ratio` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4053` `off_ball_run_type` `number` default `4.0` / catalog `4.0` | `minimum_forward_progression_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4054` `off_ball_run_type` `number` default `2.0` / catalog `2.0` | `minimum_lateral_displacement_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4055` `off_ball_run_type` `integer` default `6` / catalog `6.0` | `minimum_observed_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6312` `one_touch_relay_episode` `event_type_filter` default `Play_Pass` / catalog `Play_Pass` | `event_type_filter` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6313` `one_touch_relay_episode` `number` default `250.0` / catalog `250.0` | `max_release_alignment_ms` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6314` `one_touch_relay_episode` `number` default `3.0` / catalog `3.0` | `relay_max_event_gap_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6315` `one_touch_relay_episode` `number` default `2.75` / catalog `2.75` | `relay_touch_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6316` `one_touch_relay_episode` `number` default `0.56` / catalog `0.56` | `maximum_relay_dwell_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8989` `opponents_bypassed_by_action` `number` default `1.0` / catalog `1.0` | `goal_side_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8990` `opponents_bypassed_by_action` `number` default `1.0` / catalog `1.0` | `bypassed_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2460` `outcome_window` `number` default `8.0` / catalog `8.0` | `maximum_window_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2461` `outcome_window` `number` default `4.0` / catalog `4.0` | `minimum_settled_possession_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2462` `outcome_window` `text` default `transition_status` / catalog `transition_status` | `required_anchor_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2463` `outcome_window` `text` default `PASS` / catalog `PASS` | `required_anchor_status_value` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3717` `pairwise_distance` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3718` `pairwise_distance` `text` default `receiver_id` / catalog `receiver_id` | `entity_a_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3719` `pairwise_distance` `text` default `ball` / catalog `ball` | `entity_b_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3720` `pairwise_distance` `number` default `10.0` / catalog `10.0` | `maximum_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7967` `pressure_on_carrier` `text` default `controlled_reception_frame_id` / catalog `controlled_reception_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7968` `pressure_on_carrier` `text` default `receiver_id` / catalog `receiver_id` | `carrier_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7969` `pressure_on_carrier` `number` default `4.0` / catalog `4.0` | `maximum_pressure_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7970` `pressure_on_carrier` `number` default `0.2` / catalog `0.2` | `minimum_closing_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7971` `pressure_on_carrier` `number` default `100.0` / catalog `100.0` | `maximum_approach_angle_degrees` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7972` `pressure_on_carrier` `number` default `0.0` / catalog `0.0` | `minimum_pressure_duration_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7973` `pressure_on_carrier` `number` default `0.4` / catalog `0.4` | `lookback_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7974` `pressure_on_carrier` `text` default `defending_outfield` / catalog `defending_outfield` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:9382` `relation_destination_entry` `number` default `6.0` / catalog `6.0` | `destination_entry_horizon_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9385` `relation_destination_entry` `text` default `entry_first_then_progression` / catalog `entry_first_then_progression` | `episode_selection` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9382` `relation_destination_entry_classification` `number` default `6.0` / catalog `6.0` | `destination_entry_horizon_seconds` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:9385` `relation_destination_entry_classification` `text` default `first_by_duration_clearance` / catalog `first_by_duration_clearance` | `episode_selection` | yes | yes | added catalog default equal to old executor default; deleted executor default |
| `executor.py:6946` `relative_position_to_line` `text` default `receiver_id` / catalog `receiver_id` | `entity_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6947` `relative_position_to_line` `text` default `controlled_reception_frame_id` / catalog `controlled_reception_frame_id` | `entity_frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:6953` `relative_position_to_line` `number` default `0.5` / catalog `0.5` | `line_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3013` `set_piece_structure` `integer` default `6` / catalog `6.0` | `minimum_observed_outfield_players` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2387` `space_region_generation` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2388` `space_region_generation` `text` default `any` / catalog `any` | `zone_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2389` `space_region_generation` `number` default `8.0` / catalog `8.0` | `grid_step_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2390` `space_region_generation` `number` default `8.0` / catalog `8.0` | `minimum_opponent_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2391` `space_region_generation` `number` default `4.0` / catalog `4.0` | `minimum_teammate_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2392` `space_region_generation` `integer` default `1` / catalog `1.0` | `minimum_open_points` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2393` `space_region_generation` `integer` default `5` / catalog `5.0` | `maximum_candidate_points` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2394` `space_region_generation` `integer` default `6` / catalog `6.0` | `minimum_observed_players_per_team` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2327` `structured_zone` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2328` `structured_zone` `text` default `own_half` / catalog `own_half` | `zone_name` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2329` `structured_zone` `number` default `0.5` / catalog `0.5` | `zone_boundary_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7564` `support_arrival_relation` `text` default `controlled_reception_frame_id` / catalog `controlled_reception_frame_id` | `anchor_frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7565` `support_arrival_relation` `text` default `perspective_outfield` / catalog `perspective_outfield` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7566` `support_arrival_relation` `text` default `WITHIN_DISTANCE_OF_REFERENCE_POINT` / catalog `WITHIN_DISTANCE_OF_REFERENCE_POINT` | `support_region_mode` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7567` `support_arrival_relation` `number` default `2.0` / catalog `2.0` | `maximum_arrival_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7568` `support_arrival_relation` `number` default `0.4` / catalog `0.4` | `minimum_duration_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7569` `support_arrival_relation` `number` default `8.0` / catalog `8.0` | `maximum_support_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7570` `support_arrival_relation` `integer` default `1` / catalog `1` | `minimum_supporting_players` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7571` `support_arrival_relation` `text` default `none` / catalog `none` | `required_anchor_status_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:7572` `support_arrival_relation` `text` default `PASS` / catalog `PASS` | `required_anchor_status_value` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3441` `switch_of_play` `number` default `25.0` / catalog `25.0` | `minimum_lateral_displacement_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3442` `switch_of_play` `number` default `12.0` / catalog `12.0` | `minimum_start_lateral_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3443` `switch_of_play` `number` default `12.0` / catalog `12.0` | `minimum_end_lateral_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3444` `switch_of_play` `number` default `8.0` / catalog `8.0` | `maximum_duration_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3324` `team_compactness` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3325` `team_compactness` `text` default `defending_outfield` / catalog `defending_outfield` | `player_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3326` `team_compactness` `number` default `45.0` / catalog `45.0` | `maximum_team_width_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3327` `team_compactness` `number` default `35.0` / catalog `35.0` | `maximum_team_depth_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3328` `team_compactness` `integer` default `8` / catalog `8` | `minimum_observed_players` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8019` `team_press` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8020` `team_press` `text` default `receiver_id` / catalog `receiver_id` | `carrier_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8021` `team_press` `number` default `7.0` / catalog `7.0` | `maximum_press_distance_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8022` `team_press` `number` default `0.0` / catalog `0.0` | `minimum_closing_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8023` `team_press` `number` default `135.0` / catalog `135.0` | `maximum_approach_angle_degrees` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8024` `team_press` `integer` default `2` / catalog `2.0` | `minimum_pressing_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8025` `team_press` `number` default `30.0` / catalog `30.0` | `minimum_angle_spread_degrees` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8026` `team_press` `integer` default `6` / catalog `6.0` | `minimum_observed_defenders` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8027` `team_press` `number` default `0.4` / catalog `0.4` | `lookback_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:8028` `team_press` `text` default `defending_outfield` / catalog `defending_outfield` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4113` `time_to_arrival` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4114` `time_to_arrival` `text` default `entity` / catalog `entity` | `target_mode` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4115` `time_to_arrival` `text` default `receiver_id` / catalog `receiver_id` | `target_entity_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4116` `time_to_arrival` `text` default `reception_ball_x_m` / catalog `reception_ball_x_m` | `target_x_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4117` `time_to_arrival` `text` default `reception_ball_y_m` / catalog `reception_ball_y_m` | `target_y_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4118` `time_to_arrival` `text` default `defending_outfield` / catalog `defending_outfield` | `candidate_scope` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4119` `time_to_arrival` `number` default `2.0` / catalog `2.0` | `maximum_arrival_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4120` `time_to_arrival` `number` default `7.0` / catalog `7.0` | `maximum_player_speed_mps` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:4121` `time_to_arrival` `integer` default `1` / catalog `1` | `minimum_observed_candidates` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3690` `tracking_quality` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2220` `transition_anchor` `text` default `regain` / catalog `regain` | `transition_type` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2221` `transition_anchor` `number` default `0.4` / catalog `0.4` | `minimum_prior_possession_seconds` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2222` `transition_anchor` `text` default `any` / catalog `any` | `zone_filter` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:2223` `transition_anchor` `number` default `0.5` / catalog `0.5` | `zone_boundary_buffer_m` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3892` `velocity` `text` default `anchor_frame_id` / catalog `anchor_frame_id` | `frame_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3893` `velocity` `text` default `receiver_id` / catalog `receiver_id` | `entity_id_field` | yes | yes | deleted executor default; already catalog-resolved |
| `executor.py:3894` `velocity` `number` default `0.4` / catalog `0.4` | `lookback_seconds` | yes | yes | deleted executor default; already catalog-resolved |

## `state.params` census-only reads

These shared runtime-parameter reads remain unchanged. F2-Y owns their closure; F2-1 adds no new `state.params` reads.

| Call site | Function / capability | Read |
|---|---|---|
| `executor.py:674` | `CapabilityExecutor.execute_bound_node` / `shared predicate context` | `params=state.params,` |
| `executor.py:1563` | `legacy_m1_record_persists_for_adapter` / `shared` | `analysis_rate_hz = state.params.integer("analysis_rate_hz")` |
| `executor.py:1624` | `legacy_m1_frame_signal_persists_for_adapter` / `shared` | `analysis_rate_hz = state.params.integer("analysis_rate_hz")` |
| `executor.py:1632` | `legacy_m1_frame_signal_persists_for_adapter` / `shared` | `params=state.params,` |
| `executor.py:2192` | `primitive_possession_segment` / `possession_segment` | `minimum_frames = int(round(state.params.number("minimum_possession_seconds") * state.params.integer("analysis_rate_hz")))` |
| `executor.py:2213` | `primitive_possession_segment` / `possession_segment` | `float((end - start + 1) / state.params.integer("analysis_rate_hz")),` |
| `executor.py:2232` | `primitive_transition_anchor` / `transition_anchor` | `analysis_rate_hz = state.params.integer("analysis_rate_hz")` |
| `executor.py:2822` | `outcome_window_anchor_record` / `shared` | `analysis_rate_hz = state.params.integer("analysis_rate_hz")` |
| `executor.py:8712` | `primitive_signed_lateral_shift` / `signed_lateral_shift` | `baseline_frames = int(round(state.params.number("baseline_window_seconds") * state.params.integer("analysis_rate_hz")))` |
| `executor.py:8713` | `primitive_signed_lateral_shift` / `signed_lateral_shift` | `search_frames = int(round(state.params.number("shift_search_window_seconds") * state.params.integer("analysis_rate_hz")))` |
| `executor.py:8744` | `primitive_signed_lateral_shift` / `signed_lateral_shift` | `>= state.params.integer("minimum_outfield_players_per_team")` |
| `executor.py:8796` | `primitive_outcome_classification` / `outcome_classification` | `query_hash = state.params.text("result_id_seed_hash")` |
| `executor.py:8797` | `primitive_outcome_classification` / `outcome_classification` | `analysis_rate_hz = state.params.integer("analysis_rate_hz")` |
| `executor.py:8798` | `primitive_outcome_classification` / `outcome_classification` | `dedupe_source_frames = int(round(state.params.number("dedupe_window_seconds") * FRAME_RATE_HZ))` |
| `executor.py:8819` | `primitive_outcome_classification` / `outcome_classification` | `params=state.params,` |
| `executor.py:9125` | `relation_geometric_progressive_corridor` / `geometric_progressive_corridor` | `analysis_rate_hz=state.params.integer("analysis_rate_hz"),` |
| `executor.py:9125` | `relation_geometric_progressive_corridor` / `geometric_progressive_corridor_from_anchor_set` | `analysis_rate_hz=state.params.integer("analysis_rate_hz"),` |
| `executor.py:9385` | `primitive_relation_destination_entry_classification` / `relation_destination_entry` | `seed = str(result_seed.value) if result_seed is not None else state.params.text("result_id_seed_hash")` |
| `executor.py:9385` | `primitive_relation_destination_entry_classification` / `relation_destination_entry_classification` | `seed = str(result_seed.value) if result_seed is not None else state.params.text("result_id_seed_hash")` |
| `executor.py:9675` | `predicate_persists_for` / `shared` | `analysis_rate_hz=state.params.integer("analysis_rate_hz"),` |
| `executor.py:9716` | `wide_entry_candidates` / `shared` | `baseline_frames = int(round(state.params.number("baseline_window_seconds") * state.params.integer("analysis_rate_hz")))` |
| `executor.py:9717` | `wide_entry_candidates` / `shared` | `prior_central_threshold_m = state.params.number("prior_central_fraction") * PITCH_HALF_WIDTH_M` |
| `executor.py:9727` | `wide_entry_candidates` / `shared` | `prior_start = max(0, i - int(round(2.0 * state.params.integer("analysis_rate_hz"))))` |
| `executor.py:9742` | `wide_entry_candidates` / `shared` | `float(len(seg_frame_ids) / state.params.integer("analysis_rate_hz")),` |
| `executor.py:9747` | `wide_entry_candidates` / `shared` | `float((dwell_end - i) / state.params.integer("analysis_rate_hz")),` |
| `executor.py:9796` | `wide_entry_candidates_from_episodes` / `shared` | `round(state.params.number("minimum_wide_dwell_seconds") * state.params.integer("analysis_rate_hz"))` |

## Gate-drift enumeration

F2-1 changes catalog parameter contracts for four subjects by making 22 director-ratified defaults optional-with-default. Runtime behavior remains unchanged, and round-1 review independently confirmed **zero bound-plan hash movement** and **zero frozen-expectation hash movement**. The drift class is registry/parity cascade only: generated registry, passport, and gates that check SCP parity see stale generated artifacts until the director regenerates registry/parity at acceptance. No re-freezes are required.

| Gate | Drift class | Frozen expectation hash movement | Result / note |
|---|---|---:|---|
| `scp-0-verify` | parity-cascade root: generated registry/projections stale after parameter-contract change | 0 | **FAIL**: fresh SCP generation changes parameter contracts for the four affected subjects; generated projections and registry lock are stale by packet fence. |
| `afl-passport-verify` | parity-cascade from SCP registry/runtime revision | 0 | **FAIL**: passport projection lock, revision, and stored projection hash differ from fresh generation. |
| `afl-09a-verify` | parity-cascade through bootstrap reports checked by validation factory | 0 | **FAIL**: bootstrap factory gates fail for `AFL-08 line_break_support_response` and `AFL-08 relative_position_to_line`; branch fixture remains PASS. |
| `afl-acceleration-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-carry-episode-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-controlled-line-break-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-cover-shadow-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-defensive-line-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-lane-occupancy-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-line-break-support-response-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-local-number-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-marking-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-off-ball-run-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-off-ball-run-type-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-one-touch-pass-chain-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-relative-position-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-set-piece-structure-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-space-region-generation-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-substrate-q2-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-support-arrival-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `afl-team-press-verify` | parity-cascade | 0 | Affected by stale SCP/parity artifacts only. |
| `n1d1-verify` | none observed | 0 | **PASS**: `attestation_status=VERIFIED`, no blocking reasons. |
| `afl-substrate-q4-verify` | none observed | 0 | **PASS**: frozen expectation unchanged; result count 2, signature `89cc48842fc6b9852fc6941fc56e2147e524de7a2d3ae7fe718d29c96d382199`. |
| `afl-substrate-q6-verify` | none observed | 0 | **PASS**: frozen expectation unchanged; result count 0, signature `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`. |

The combined gate command stops at `scp-0-verify`, so downstream pass/fail rows were run individually where round 1 had committed-tree evidence. The additional parity-cascade rows above are from the round-1 rejection review's complete gate sweep against commit `e491997`.

## Full-suite table

| Command | Result |
|---|---|
| `PYTHONPATH=src .venv/bin/python -m unittest tests.test_executor_boundaries` | **PASS**: 5 tests. |
| `PYTHONPATH=src .venv/bin/python -m py_compile src/tqe/runtime/executor.py src/tqe/runtime/catalog.py` | **PASS**. |
| Node-parameter arity scan | **PASS**: no `node_parameter_number/integer/text` call has executor-default arity. |
| `make envelope-conformance-report` | **PASS**: 2544 findings, unchanged by this packet. |
| `make scp-0-verify` | **FAIL**: expected generated projection / registry-lock drift from catalog default declarations; see gate table. |
| `make afl-passport-verify` | **FAIL**: expected passport projection drift from the SCP registry/runtime revision; see gate table. |
| `make afl-09a-verify` | **FAIL**: expected frozen bootstrap expectation drift for two AFL-08 bootstrap targets; see gate table. |
| `make n1d1-verify` | **PASS**. |
| `make afl-substrate-q4-verify` | **PASS**. |
| `make afl-substrate-q6-verify` | **PASS**. |
| `make test` | **FAIL**: 350 tests, 5 failures. All five are generated/SCP drift failures: `test_generated_artifacts_are_current`; `test_canonical_product_shared_records_have_no_contract_drift`; `test_checked_in_lock_and_parity_report_match_fresh_regeneration`; `test_scp0_generation_passes_and_excludes_atlas_from_product_and_ai`; `test_scp0_verifier_check_mode_leaves_tracked_files_untouched`. |
