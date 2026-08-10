APP_KEY="lean"; NAME="The Lean Rush"; SCHEMA_VERSION=1
MANIFEST={"app_key":APP_KEY,"name":NAME,"schema_version":SCHEMA_VERSION,"params":{
  "slow_station_bias":{"type":"list","default":["Blender","Blender","Fruit","Finish"],"group":"Scenario","label":"Bottleneck bias pool"},
  "slow_mult_range":{"type":"list","default":[1.25,1.60],"group":"Scenario","label":"Bottleneck slowdown range"},
  "demand_mix":{"type":"list","default":["Light","Normal","Normal","Slammed"],"group":"Scenario","label":"Rush intensity pool"},
  "demand_mult_range":{"type":"list","default":[0.90,1.15],"group":"Scenario","label":"Demand multiplier range"},
  "patience_choices":{"type":"list","default":[120,135,150,170,190],"group":"Scenario","label":"Customer patience (s)"},
  "defect_base_range":{"type":"list","default":[0.12,0.20],"group":"Scenario","label":"Baseline defect range"},
  "start_batch_choices":{"type":"list","default":[2,3,4],"group":"Scenario","label":"Inherited batch sizes"},
  "start_premade_choices":{"type":"list","default":[6,8,10,12],"group":"Scenario","label":"Inherited made-ahead pile"},
  "horizon_s":{"type":"float","default":900.0,"min":60,"group":"Rush","label":"Rush length (s)"},
  "blend_setup":{"type":"float","default":6.0,"min":0,"group":"Rush","label":"Blend setup (s)"},
  "handoff_time":{"type":"float","default":2.0,"min":0,"group":"Rush","label":"Handoff time (s)"},
  "lean_target":{"type":"int","default":70,"min":0,"max":100,"group":"Grading","label":"Lean score to finish"},
  "profit_target":{"type":"float","default":0.0,"group":"Grading","label":"Profit required"},
}}
