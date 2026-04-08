import csv
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.datasets import load_iris

from core.rpc.models import RPCError
from core.rpc_service import NodeRPCService


def auth(user: str, is_admin: bool = False):
    return {
        "user": user,
        "user_address": user,
        "is_admin": is_admin,
    }


def iris_csv_bytes() -> bytes:
    ds = load_iris()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(ds.feature_names + ["target", "target_name"])
    for row, target in zip(ds.data, ds.target):
        writer.writerow(list(row) + [int(target), ds.target_names[int(target)]])
    return out.getvalue().encode("utf-8")


def main() -> None:
    service = NodeRPCService()

    buyer = "buyer_public_demo"
    miner = "miner_public_demo"

    payload = iris_csv_bytes()
    checksum = hashlib.sha256(payload).hexdigest()

    init = service._file_init_upload(
        filename="iris.csv",
        totalSize=len(payload),
        checksumSha256=checksum,
        auth_context=auth(buyer),
    )
    upload_id = init["uploadId"]

    import base64

    service._file_upload_chunk(
        uploadId=upload_id,
        chunkIndex=0,
        data=base64.b64encode(payload).decode("ascii"),
        auth_context=auth(buyer),
    )

    finalized = service._file_finalize_upload(
        uploadId=upload_id,
        auth_context=auth(buyer),
    )
    file_ref = finalized["fileRef"]

    denied_other_file_info = False
    try:
        service._file_get_info(fileRef=file_ref, auth_context=auth(miner))
    except RPCError:
        denied_other_file_info = True

    submit = service._compute_submit_order(
        gpu_type="CPU",
        gpu_count=1,
        price_per_hour=0,
        duration_hours=1,
        free_order=True,
        buyer_address=buyer,
        inputDataRef=file_ref,
        inputFilename="iris.csv",
        program="result={'status':'ok','dataset':'iris','rows':150}",
    )
    order_id = submit["orderId"]

    accepted = service._compute_accept_order(
        order_id=order_id,
        miner_address=miner,
    )
    task_id = accepted["taskId"]

    completed = service._compute_complete_order(
        order_id=order_id,
        task_id=task_id,
        result_data="",
    )

    buyer_outputs = service._task_get_outputs(task_id=task_id, auth_context=auth(buyer))

    denied_non_owner_outputs = False
    try:
        service._task_get_outputs(task_id=task_id, auth_context=auth(miner))
    except RPCError:
        denied_non_owner_outputs = True

    summary = {
        "dataset": "iris",
        "rows": 150,
        "fileRef": file_ref,
        "orderId": order_id,
        "taskId": task_id,
        "completed": completed.get("status") == "success",
        "resultReturned": bool(buyer_outputs),
        "ownerOnlyFileInfoEnforced": denied_other_file_info,
        "ownerOnlyResultEnforced": denied_non_owner_outputs,
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
