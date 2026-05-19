import base64
import ddm_pb2

data = "CQAAAPPaf9pBEQAAAAAAAAAAGiIKFVNvbGFyQW5nbGVfQ0ppbnB1dFswXRADGQAAAGC4HglAGiIKFVNvbGFyQW5nbGVfQ0ppbnB1dFsxXRADGQAAACBcjxBAGiIKFVNvbGFyQW5nbGVfQ0ppbnB1dFsyXRADGQAAACBcjxRA"
decoded = base64.b64decode(data)
pb_data = ddm_pb2.DDMData()
pb_data.ParseFromString(decoded)

print(f"Sim Time: {pb_data.sim_time}")
for v in pb_data.sim_vars:
    print(f"Var: {v.name} = {v.double_value}")
