import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from utils.login import login_required, op_required
from utils.mysql import connect

dynamic_components_page = Blueprint("dynamic_components", __name__)

VALID_COMPONENT_KEYS = {"title", "swiper"}


def _normalize_component_key(raw_key):
    return raw_key if raw_key in VALID_COMPONENT_KEYS else None


def _load_component_content(key):
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT content FROM `dynamic_components` WHERE name=%s",
                (key,),
            )
            result = cursor.fetchone()
            if result is None:
                return None

            content = result.get("content")
            return json.loads(content) if isinstance(content, str) else content
    finally:
        connection.close()


def _parse_request_json(raw_data):
    try:
        return json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload") from exc


def _validate_swiper_payload(data_obj):
    if not isinstance(data_obj, dict):
        raise ValueError("Invalid swiper payload")

    images = data_obj.get("images")
    if not isinstance(images, list):
        raise ValueError("Swiper payload must include an images array")

    for index, image_info in enumerate(images, start=1):
        if not isinstance(image_info, dict):
            raise ValueError(f"Image #{index} must be an object")
        if not image_info.get("url"):
            raise ValueError(f"Image #{index} is missing url")

    metadata = data_obj.get("metadata")
    if metadata is None:
        data_obj["metadata"] = {}
        metadata = data_obj["metadata"]
    elif not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")

    metadata["lastModified"] = datetime.now().isoformat() + "Z"
    return data_obj


def _validate_title_payload(data_obj, refresh_timestamp=False):
    if not isinstance(data_obj, dict):
        raise ValueError("Title layout payload must be an object")

    nodes = data_obj.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Title layout payload must include a nodes array")

    normalized_nodes = []
    seen_node_ids = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"nodes[{index}] must be an object")

        node_id = node.get("id")
        if not isinstance(node_id, int):
            raise ValueError(f"nodes[{index}].id must be an integer")
        if node_id in seen_node_ids:
            raise ValueError(f"Duplicate node id: {node_id}")
        seen_node_ids.add(node_id)

        title = node.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"nodes[{index}].title cannot be empty")

        level = node.get("level")
        if level not in (1, 2):
            raise ValueError(f"nodes[{index}].level must be 1 or 2")

        x = node.get("x")
        y = node.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"nodes[{index}].x and nodes[{index}].y must be numeric")

        parent_id = node.get("parentId")
        if level == 1:
            parent_id = None
        elif not isinstance(parent_id, int):
            raise ValueError(f"nodes[{index}].parentId must point to a level-1 node")

        icon_url = node.get("iconUrl")
        if icon_url is not None and not isinstance(icon_url, str):
            raise ValueError(f"nodes[{index}].iconUrl must be a string or null")

        product_uuids = node.get("productUuids") or []
        if not isinstance(product_uuids, list):
            raise ValueError(f"nodes[{index}].productUuids must be a string array")

        normalized_product_uuids = []
        seen_product_uuids = set()
        for product_index, product_uuid in enumerate(product_uuids):
            if not isinstance(product_uuid, str) or not product_uuid.strip():
                raise ValueError(
                    f"nodes[{index}].productUuids[{product_index}] must be a non-empty string"
                )
            product_uuid = product_uuid.strip()
            if product_uuid in seen_product_uuids:
                continue
            seen_product_uuids.add(product_uuid)
            normalized_product_uuids.append(product_uuid)

        normalized_nodes.append(
            {
                "id": node_id,
                "title": title.strip(),
                "level": level,
                "x": x,
                "y": y,
                "parentId": parent_id,
                "iconUrl": icon_url,
                "productUuids": normalized_product_uuids,
            }
        )

    node_map = {node["id"]: node for node in normalized_nodes}
    for node in normalized_nodes:
        if node["level"] != 2:
            continue
        parent = node_map.get(node["parentId"])
        if parent is None:
            raise ValueError(f"Level-2 node {node['id']} references a missing parentId")
        if parent["level"] != 1:
            raise ValueError(f"Level-2 node {node['id']} must reference a level-1 parent")

    normalized_data = dict(data_obj)
    normalized_data["nodes"] = normalized_nodes

    metadata = normalized_data.get("metadata")
    if metadata is None:
        normalized_data["metadata"] = {}
        metadata = normalized_data["metadata"]
    elif not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")

    if refresh_timestamp:
        metadata["lastModified"] = datetime.now().isoformat() + "Z"

    return normalized_data


def _build_directory_path(node, node_map):
    path = []
    current = node
    visited = set()

    while current is not None:
        current_id = current["id"]
        if current_id in visited:
            raise ValueError("Title layout contains a cyclic parent reference")
        visited.add(current_id)

        path.append(
            {
                "id": current_id,
                "title": current["title"],
                "level": current["level"],
            }
        )

        parent_id = current.get("parentId")
        current = node_map.get(parent_id) if parent_id is not None else None

    path.reverse()
    return path


@dynamic_components_page.route("/get/", methods=["GET"])
def get_components():
    key = _normalize_component_key(request.args.get("key", ""))
    if not key:
        return jsonify({"code": 400, "message": "Invalid key"}), 400

    try:
        result = _load_component_content(key)
        if result is None:
            return {"code": 404, "message": "Component not found"}, 404
        return {"code": 200, "data": result}, 200
    except Exception as exc:
        return jsonify({"code": 500, "message": f"Failed to load component: {exc}"}), 500


@dynamic_components_page.route("/title/product-directories/<product_uuid>/", methods=["GET"])
def get_product_directories(product_uuid):
    if not product_uuid:
        return jsonify({"code": 400, "message": "Missing product_uuid"}), 400

    try:
        result = _load_component_content("title")
        if result is None:
            return jsonify({"code": 404, "message": "Title layout not found"}), 404

        title_data = _validate_title_payload(result, refresh_timestamp=False)
        nodes = title_data.get("nodes", [])
        node_map = {node["id"]: node for node in nodes}

        matches = []
        for node in nodes:
            if product_uuid not in node.get("productUuids", []):
                continue

            path = _build_directory_path(node, node_map)
            matches.append(
                {
                    "node_id": node["id"],
                    "node_title": node["title"],
                    "node_level": node["level"],
                    "parent_id": node.get("parentId"),
                    "path": path,
                    "path_text": " / ".join(item["title"] for item in path),
                }
            )

        matches.sort(key=lambda item: (len(item["path"]), item["path_text"]))

        return (
            jsonify(
                {
                    "code": 200,
                    "data": {
                        "product_uuid": product_uuid,
                        "count": len(matches),
                        "matches": matches,
                    },
                }
            ),
            200,
        )
    except ValueError as exc:
        return jsonify({"code": 500, "message": f"Invalid title layout data: {exc}"}), 500
    except Exception as exc:
        return jsonify({"code": 500, "message": f"Failed to load title layout: {exc}"}), 500


@dynamic_components_page.route("/update/", methods=["POST"])
@login_required
@op_required
def add_components():
    print("request.form:", request.form)

    key = _normalize_component_key(request.form.get("key", ""))
    data = request.form.get("data", {})

    if not key:
        return jsonify({"code": 400, "message": "Invalid key"}), 400

    try:
        data_obj = _parse_request_json(data)
        if key == "title":
            data_obj = _validate_title_payload(data_obj, refresh_timestamp=True)
        else:
            data_obj = _validate_swiper_payload(data_obj)
        data = json.dumps(data_obj, ensure_ascii=False)
    except ValueError as exc:
        return jsonify({"code": 400, "message": str(exc)}), 400

    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE `dynamic_components`
                SET content = %s
                WHERE name = %s
                """,
                (data, key),
            )
        connection.commit()
    except Exception as exc:
        return jsonify({"code": 500, "message": f"Failed to save component: {exc}"}), 500
    finally:
        connection.close()

    return jsonify({"code": 200, "message": "Updated", "data": json.loads(data)}), 200
