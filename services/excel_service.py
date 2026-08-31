import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from database.mongodb import (
    get_products_collection,
    get_procurement_collection,
    get_expenses_collection,
    get_imports_collection,
    init_mongo_indexes,
)
from excel.parser import (
    read_excel_sheets,
    find_header_row,
    resolve_column_indices,
    is_dummy_sheet,
    parse_numeric,
    parse_int_qty,
    parse_date_value,
)
from excel.normalizer import (
    normalize_text,
    clean_display_name,
    extract_keywords_and_aliases,
)
from excel.categorizer import (
    extract_category_and_subcategory,
)
from excel.deduplicator import (
    compute_row_hash,
)

logger = logging.getLogger("services.excel")


def process_procurement_data(
    file_bytes: bytes,
    filename: str,
    uploaded_by: str = "admin"
) -> Dict[str, Any]:
    """
    Process Procurement / Requirements Workbook.
    Assigns unique import_batch_id, retains metadata, ensures idempotency.
    """
    init_mongo_indexes()
    products_col = get_products_collection()
    procurement_col = get_procurement_collection()
    imports_col = get_imports_collection()

    sheets = read_excel_sheets(file_bytes)
    import_batch_id = f"batch_proc_{uuid.uuid4().hex[:12]}"
    
    import_record = {
        "import_batch_id": import_batch_id,
        "filename": filename,
        "file_type": "procurement",
        "source_type": "excel_import",
        "upload_timestamp": datetime.utcnow(),
        "uploaded_by": uploaded_by,
        "total_rows": 0,
        "valid_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "duplicate_records": 0,
        "rejected_records": 0,
        "errors": [],
        "status": "in_progress",
    }
    import_id = imports_col.insert_one(import_record).inserted_id

    total_rows = 0
    new_products_cnt = 0
    updated_products_cnt = 0
    duplicate_rows_cnt = 0
    valid_records_cnt = 0
    errors = []

    try:
        for sheet_name, rows in sheets.items():
            if is_dummy_sheet(sheet_name, rows):
                logger.info("Skipping dummy tab in procurement workbook: %s", sheet_name)
                continue

            if not rows or len(rows) < 2:
                continue

            header_idx, col_map = find_header_row(rows)
            if not col_map:
                continue

            cols = resolve_column_indices(col_map)
            name_idx = cols["name"]
            id_idx = cols["id"]
            cat_idx = cols["category"]
            subcat_idx = cols["sub_category"]
            details_idx = cols["details"]
            qty_idx = cols["qty"]
            amount_idx = cols["amount"]
            price_idx = cols["price"]
            min_stock_idx = cols["min_stock"]
            market_idx = cols["market"]
            order_date_idx = cols["date"]
            order_status_idx = cols["status"]
            vendor_idx = cols["vendor"]
            approved_by_idx = cols["approved_by"]
            remarks_idx = cols["remarks"]
            issued_by_idx = cols["issued_by"]
            url_idx = cols["url"]

            for r_idx in range(header_idx + 1, len(rows)):
                row = rows[r_idx]
                if not row or not any(row):
                    continue

                total_rows += 1
                raw_name = row[name_idx] if name_idx is not None and name_idx < len(row) else None
                if not raw_name or str(raw_name).strip() == "":
                    continue

                clean_name = clean_display_name(raw_name)
                norm_name = normalize_text(clean_name)
                if not norm_name:
                    continue

                row_cat = str(row[cat_idx]).strip() if cat_idx is not None and cat_idx < len(row) and row[cat_idx] is not None else None
                row_subcat = str(row[subcat_idx]).strip() if subcat_idx is not None and subcat_idx < len(row) and row[subcat_idx] is not None else None

                details = str(row[details_idx]).strip() if details_idx is not None and details_idx < len(row) and row[details_idx] is not None else ""
                qty = parse_int_qty(row[qty_idx] if qty_idx is not None and qty_idx < len(row) else 1, default=1)
                unit_price = parse_numeric(row[price_idx] if price_idx is not None and price_idx < len(row) else 0.0)
                amount = parse_numeric(row[amount_idx] if amount_idx is not None and amount_idx < len(row) else (qty * unit_price))
                min_stock_val = parse_int_qty(row[min_stock_idx] if min_stock_idx is not None and min_stock_idx < len(row) else max(3, int(qty * 0.5)), default=max(3, int(qty * 0.5)))
                market = str(row[market_idx]).strip() if market_idx is not None and market_idx < len(row) and row[market_idx] is not None else "General"
                
                raw_date = row[order_date_idx] if order_date_idx is not None and order_date_idx < len(row) else None
                dt_obj, date_str = parse_date_value(raw_date)

                order_status = str(row[order_status_idx]).strip() if order_status_idx is not None and order_status_idx < len(row) and row[order_status_idx] is not None else "Pending"
                vendor = str(row[vendor_idx]).strip() if vendor_idx is not None and vendor_idx < len(row) and row[vendor_idx] is not None else "Standard Vendor"
                approved_by = str(row[approved_by_idx]).strip() if approved_by_idx is not None and approved_by_idx < len(row) and row[approved_by_idx] is not None else ""
                remarks = str(row[remarks_idx]).strip() if remarks_idx is not None and remarks_idx < len(row) and row[remarks_idx] is not None else ""
                issued_by = str(row[issued_by_idx]).strip() if issued_by_idx is not None and issued_by_idx < len(row) and row[issued_by_idx] is not None else ""
                url = str(row[url_idx]).strip() if url_idx is not None and url_idx < len(row) and row[url_idx] is not None else ""

                category, sub_category = extract_category_and_subcategory(
                    filename=filename,
                    sheet_name=sheet_name,
                    item_name=clean_name,
                    details=details or remarks,
                    row_category=row_cat,
                    row_subcategory=row_subcat,
                )

                row_hash = compute_row_hash(norm_name, qty, amount, date_str, vendor, order_status, remarks, sheet_name)

                existing_proc = procurement_col.find_one({"row_hash": row_hash})
                if existing_proc:
                    duplicate_rows_cnt += 1
                    logger.debug("Duplicate procurement row skipped: %s (%s)", clean_name, row_hash)
                    continue

                valid_records_cnt += 1
                keywords, aliases = extract_keywords_and_aliases(clean_name, details, remarks)

                existing_prod = products_col.find_one({"normalized_name": norm_name})
                
                if existing_prod:
                    updated_products_cnt += 1
                    prod_id = existing_prod["_id"]
                    
                    merged_keywords = sorted(list(set(existing_prod.get("keywords", []) + keywords)))
                    merged_aliases = sorted(list(set(existing_prod.get("aliases", []) + aliases)))
                    merged_sources = list(set(existing_prod.get("source_files", []) + [filename]))
                    merged_batches = list(set(existing_prod.get("import_batch_ids", []) + [import_batch_id]))

                    stock_delta = qty if order_status.lower() == "fulfilled" else 0
                    pending_delta = qty if order_status.lower() in ("pending", "approved") else 0

                    update_fields = {
                        "updated_at": datetime.utcnow(),
                        "keywords": merged_keywords,
                        "aliases": merged_aliases,
                        "source_files": merged_sources,
                        "import_batch_ids": merged_batches,
                    }
                    if category and (not existing_prod.get("category") or existing_prod.get("category") in ("General", "General Supplies")):
                        update_fields["category"] = category
                    if sub_category and not existing_prod.get("sub_category"):
                        update_fields["sub_category"] = sub_category
                    if details and not existing_prod.get("details"):
                        update_fields["details"] = details
                    if vendor and (not existing_prod.get("supplier") or existing_prod.get("supplier") in ("Standard Vendor", "Corporate Vendor")):
                        update_fields["supplier"] = vendor
                    if market:
                        update_fields["market"] = market
                    if unit_price > 0 and (not existing_prod.get("unit_price") or existing_prod.get("unit_price") == 0.0):
                        update_fields["unit_price"] = unit_price

                    products_col.update_one(
                        {"_id": prod_id},
                        {
                            "$set": update_fields,
                            "$inc": {
                                "current_stock": stock_delta,
                                "total_qty_required": qty,
                                "pending_requirements": pending_delta,
                            }
                        }
                    )
                else:
                    new_products_cnt += 1
                    initial_stock = qty if order_status.lower() == "fulfilled" else max(qty, 5)
                    pending_qty = qty if order_status.lower() in ("pending", "approved") else 0
                    
                    new_product_doc = {
                        "name": clean_name,
                        "normalized_name": norm_name,
                        "details": details,
                        "aliases": aliases,
                        "keywords": keywords,
                        "category": category,
                        "sub_category": sub_category,
                        "current_stock": initial_stock,
                        "min_stock": min_stock_val,
                        "unit_price": unit_price if unit_price > 0 else (amount / qty if qty else 0),
                        "supplier": vendor,
                        "market": market,
                        "status": "low_stock" if initial_stock <= min_stock_val else "in_stock",
                        "total_expense": amount if order_status.lower() == "fulfilled" else 0,
                        "total_qty_purchased": qty if order_status.lower() == "fulfilled" else 0,
                        "total_qty_required": qty,
                        "pending_requirements": pending_qty,
                        "source_type": "excel_import",
                        "created_by_import_id": import_batch_id,
                        "import_batch_ids": [import_batch_id],
                        "source_files": [filename],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                    prod_id = products_col.insert_one(new_product_doc).inserted_id

                proc_record = {
                    "product_id": prod_id,
                    "product_name": clean_name,
                    "normalized_name": norm_name,
                    "category": category,
                    "sub_category": sub_category,
                    "details": details,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "amount": amount,
                    "market": market,
                    "order_date": dt_obj,
                    "order_date_str": date_str,
                    "order_status": order_status,
                    "vendor_name": vendor,
                    "approved_by": approved_by,
                    "remarks": remarks,
                    "requirement_issued_by": issued_by,
                    "url": url,
                    "source_type": "excel_import",
                    "source_file": filename,
                    "source_sheet": sheet_name,
                    "import_id": import_id,
                    "import_batch_id": import_batch_id,
                    "row_hash": row_hash,
                    "created_at": datetime.utcnow(),
                }
                procurement_col.insert_one(proc_record)

        for prod in products_col.find({}):
            cur = prod.get("current_stock", 0)
            mins = prod.get("min_stock", 5)
            status_str = "out_of_stock" if cur == 0 else ("low_stock" if cur <= mins else "in_stock")
            products_col.update_one({"_id": prod["_id"]}, {"$set": {"status": status_str}})

        imports_col.update_one(
            {"_id": import_id},
            {
                "$set": {
                    "total_rows": total_rows,
                    "valid_records": valid_records_cnt,
                    "new_records": new_products_cnt,
                    "updated_records": updated_products_cnt,
                    "duplicate_records": duplicate_rows_cnt,
                    "rejected_records": total_rows - (valid_records_cnt + duplicate_rows_cnt),
                    "errors": errors,
                    "status": "completed",
                }
            }
        )

        return {
            "success": True,
            "filename": filename,
            "file_type": "procurement",
            "import_batch_id": import_batch_id,
            "total_rows": total_rows,
            "valid_records": valid_records_cnt,
            "new_records": new_products_cnt,
            "updated_records": updated_products_cnt,
            "duplicate_records": duplicate_rows_cnt,
            "errors": errors,
            "import_id": str(import_id),
        }

    except Exception as e:
        logger.exception("Error in process_procurement_data: %s", e)
        imports_col.update_one(
            {"_id": import_id},
            {"$set": {"status": "failed", "errors": [str(e)]}}
        )
        raise e


def process_expenses_data(
    file_bytes: bytes,
    filename: str,
    uploaded_by: str = "admin"
) -> Dict[str, Any]:
    """
    Process Expenses Workbook.
    Assigns unique import_batch_id, retains metadata, ensures idempotency.
    """
    init_mongo_indexes()
    products_col = get_products_collection()
    expenses_col = get_expenses_collection()
    imports_col = get_imports_collection()

    sheets = read_excel_sheets(file_bytes)
    import_batch_id = f"batch_exp_{uuid.uuid4().hex[:12]}"

    import_record = {
        "import_batch_id": import_batch_id,
        "filename": filename,
        "file_type": "expenses",
        "source_type": "excel_import",
        "upload_timestamp": datetime.utcnow(),
        "uploaded_by": uploaded_by,
        "total_rows": 0,
        "valid_records": 0,
        "new_records": 0,
        "updated_records": 0,
        "duplicate_records": 0,
        "rejected_records": 0,
        "errors": [],
        "status": "in_progress",
    }
    import_id = imports_col.insert_one(import_record).inserted_id

    total_rows = 0
    new_products_cnt = 0
    updated_products_cnt = 0
    duplicate_rows_cnt = 0
    valid_records_cnt = 0
    errors = []

    try:
        for sheet_name, rows in sheets.items():
            if is_dummy_sheet(sheet_name, rows):
                logger.info("Skipping non-expense tab: %s", sheet_name)
                continue

            if not rows or len(rows) < 2:
                continue

            header_idx, col_map = find_header_row(rows)
            if not col_map:
                continue

            cols = resolve_column_indices(col_map)
            comp_idx = cols["name"]
            id_idx = cols["id"]
            cat_idx = cols["category"]
            subcat_idx = cols["sub_category"]
            qty_idx = cols["qty"]
            unit_price_idx = cols["price"]
            date_idx = cols["date"]
            amount_idx = cols["amount"]
            min_stock_idx = cols["min_stock"]
            status_idx = cols["status"]
            remark_idx = cols["remarks"] if cols["remarks"] is not None else cols["details"]
            vendor_idx = cols["vendor"]

            for r_idx in range(header_idx + 1, len(rows)):
                row = rows[r_idx]
                if not row or not any(row):
                    continue

                total_rows += 1
                raw_comp = row[comp_idx] if comp_idx is not None and comp_idx < len(row) else None
                if not raw_comp or str(raw_comp).strip() == "":
                    continue

                clean_name = clean_display_name(raw_comp)
                norm_name = normalize_text(clean_name)
                if not norm_name:
                    continue

                row_cat = str(row[cat_idx]).strip() if cat_idx is not None and cat_idx < len(row) and row[cat_idx] is not None else None
                row_subcat = str(row[subcat_idx]).strip() if subcat_idx is not None and subcat_idx < len(row) and row[subcat_idx] is not None else None
                vendor = str(row[vendor_idx]).strip() if vendor_idx is not None and vendor_idx < len(row) and row[vendor_idx] is not None else "Corporate Vendor"

                qty = parse_int_qty(row[qty_idx] if qty_idx is not None and qty_idx < len(row) else 1, default=1)
                unit_price = parse_numeric(row[unit_price_idx] if unit_price_idx is not None and unit_price_idx < len(row) else 0.0)
                amount = parse_numeric(row[amount_idx] if amount_idx is not None and amount_idx < len(row) else (qty * unit_price))
                min_stock_val = parse_int_qty(row[min_stock_idx] if min_stock_idx is not None and min_stock_idx < len(row) else max(3, int(qty * 0.5)), default=max(3, int(qty * 0.5)))
                
                raw_date = row[date_idx] if date_idx is not None and date_idx < len(row) else None
                dt_obj, date_str = parse_date_value(raw_date)

                status = str(row[status_idx]).strip() if status_idx is not None and status_idx < len(row) and row[status_idx] is not None else "Paid"
                remark = str(row[remark_idx]).strip() if remark_idx is not None and remark_idx < len(row) and row[remark_idx] is not None else ""

                category, sub_category = extract_category_and_subcategory(
                    filename=filename,
                    sheet_name=sheet_name,
                    item_name=clean_name,
                    details=remark,
                    row_category=row_cat,
                    row_subcategory=row_subcat,
                )

                row_hash = compute_row_hash(norm_name, qty, amount, unit_price, date_str, sheet_name, status, remark)

                existing_exp = expenses_col.find_one({"row_hash": row_hash})
                if existing_exp:
                    duplicate_rows_cnt += 1
                    logger.debug("Duplicate expense row skipped: %s (%s)", clean_name, row_hash)
                    continue

                valid_records_cnt += 1
                keywords, aliases = extract_keywords_and_aliases(clean_name, remark)

                existing_prod = products_col.find_one({"normalized_name": norm_name})

                if existing_prod:
                    updated_products_cnt += 1
                    prod_id = existing_prod["_id"]
                    
                    merged_keywords = sorted(list(set(existing_prod.get("keywords", []) + keywords)))
                    merged_aliases = sorted(list(set(existing_prod.get("aliases", []) + aliases)))
                    merged_sources = list(set(existing_prod.get("source_files", []) + [filename]))
                    merged_batches = list(set(existing_prod.get("import_batch_ids", []) + [import_batch_id]))

                    stock_delta = qty if status.lower() == "paid" else 0

                    update_fields = {
                        "updated_at": datetime.utcnow(),
                        "keywords": merged_keywords,
                        "aliases": merged_aliases,
                        "source_files": merged_sources,
                        "import_batch_ids": merged_batches,
                    }
                    if category and (not existing_prod.get("category") or existing_prod.get("category") in ("General", "General Supplies")):
                        update_fields["category"] = category
                    if sub_category and not existing_prod.get("sub_category"):
                        update_fields["sub_category"] = sub_category
                    if unit_price > 0 and (not existing_prod.get("unit_price") or existing_prod.get("unit_price") == 0.0):
                        update_fields["unit_price"] = unit_price
                    if remark and not existing_prod.get("details"):
                        update_fields["details"] = remark

                    products_col.update_one(
                        {"_id": prod_id},
                        {
                            "$set": update_fields,
                            "$inc": {
                                "current_stock": stock_delta,
                                "total_expense": amount,
                                "total_qty_purchased": qty,
                            }
                        }
                    )
                else:
                    new_products_cnt += 1
                    initial_stock = qty if status.lower() == "paid" else max(qty, 5)
                    
                    new_product_doc = {
                        "name": clean_name,
                        "normalized_name": norm_name,
                        "details": remark,
                        "aliases": aliases,
                        "keywords": keywords,
                        "category": category,
                        "sub_category": sub_category,
                        "current_stock": initial_stock,
                        "min_stock": min_stock_val,
                        "unit_price": unit_price if unit_price > 0 else (amount / qty if qty else 0),
                        "supplier": vendor,
                        "market": "Direct",
                        "status": "low_stock" if initial_stock <= min_stock_val else "in_stock",
                        "total_expense": amount,
                        "total_qty_purchased": qty,
                        "total_qty_required": 0,
                        "pending_requirements": 0,
                        "source_type": "excel_import",
                        "created_by_import_id": import_batch_id,
                        "import_batch_ids": [import_batch_id],
                        "source_files": [filename],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                    prod_id = products_col.insert_one(new_product_doc).inserted_id

                exp_record = {
                    "product_id": prod_id,
                    "product_name": clean_name,
                    "normalized_name": norm_name,
                    "category": category,
                    "sub_category": sub_category,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "date": dt_obj,
                    "date_str": date_str,
                    "amount": amount,
                    "status": status,
                    "remark": remark,
                    "expense_month": sheet_name,
                    "source_type": "excel_import",
                    "source_file": filename,
                    "source_sheet": sheet_name,
                    "import_id": import_id,
                    "import_batch_id": import_batch_id,
                    "row_hash": row_hash,
                    "created_at": datetime.utcnow(),
                }
                expenses_col.insert_one(exp_record)

        for prod in products_col.find({}):
            cur = prod.get("current_stock", 0)
            mins = prod.get("min_stock", 5)
            status_str = "out_of_stock" if cur == 0 else ("low_stock" if cur <= mins else "in_stock")
            products_col.update_one({"_id": prod["_id"]}, {"$set": {"status": status_str}})

        imports_col.update_one(
            {"_id": import_id},
            {
                "$set": {
                    "total_rows": total_rows,
                    "valid_records": valid_records_cnt,
                    "new_records": new_products_cnt,
                    "updated_records": updated_products_cnt,
                    "duplicate_records": duplicate_rows_cnt,
                    "rejected_records": total_rows - (valid_records_cnt + duplicate_rows_cnt),
                    "errors": errors,
                    "status": "completed",
                }
            }
        )

        return {
            "success": True,
            "filename": filename,
            "file_type": "expenses",
            "import_batch_id": import_batch_id,
            "total_rows": total_rows,
            "valid_records": valid_records_cnt,
            "new_records": new_products_cnt,
            "updated_records": updated_products_cnt,
            "duplicate_records": duplicate_rows_cnt,
            "errors": errors,
            "import_id": str(import_id),
        }

    except Exception as e:
        logger.exception("Error in process_expenses_data: %s", e)
        imports_col.update_one(
            {"_id": import_id},
            {"$set": {"status": "failed", "errors": [str(e)]}}
        )
        raise e


def auto_detect_and_import(file_bytes: bytes, filename: str, uploaded_by: str = "admin") -> Dict[str, Any]:
    """
    Intelligently detect whether an uploaded file is Procurement or Expenses and process it.
    """
    sheets = read_excel_sheets(file_bytes)
    sheet_names_lower = [s.lower() for s in sheets.keys()]

    if any("expense" in s for s in sheet_names_lower):
        return process_expenses_data(file_bytes, filename, uploaded_by)

    for name, rows in sheets.items():
        if not rows or len(rows) < 2:
            continue
        _, col_map = find_header_row(rows)
        if any("approved" in c or "vendor" in c or "market" in c for c in col_map.keys()):
            return process_procurement_data(file_bytes, filename, uploaded_by)

    first_sheet = next(iter(sheets.values()))
    _, col_map = find_header_row(first_sheet)
    if "amount" in col_map and "unit price" in col_map:
        return process_expenses_data(file_bytes, filename, uploaded_by)

    return process_procurement_data(file_bytes, filename, uploaded_by)
