import csv
import io
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.api.dependencies import require_permission
from app.models.employee_inactive import EmployeeInactive
from app.models.employee2 import Employee2
from app.schemas.employee_inactive import (
    EmployeeInactive as EmployeeInactiveSchema,
    EmployeeInactiveCreate,
    EmployeeInactiveList,
    EmployeeInactiveUpdate,
)

router = APIRouter(dependencies=[Depends(require_permission("employees:view"))])


def _excel_date_to_str(serial):
    if not serial:
        return None
    try:
        # Excel date serial to human readable (approx)
        # 1900-01-01 is 1
        val = float(serial)
        if val < 59: # Before Feb 28 1900
            d = datetime(1899, 12, 31) + timedelta(days=val)
        else:
            d = datetime(1899, 12, 30) + timedelta(days=val)
        return d.strftime("%Y-%m-%d")
    except:
        return str(serial)


@router.get("/", response_model=EmployeeInactiveList)
async def list_inactive_employees(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(EmployeeInactive)
    if search:
        search_filter = or_(
            EmployeeInactive.name.ilike(f"%{search}%"),
            EmployeeInactive.fss_no.ilike(f"%{search}%"),
            EmployeeInactive.cnic.ilike(f"%{search}%"),
            EmployeeInactive.mobile_no.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)
    
    total = query.count()
    employees = query.order_by(EmployeeInactive.id.desc()).offset(skip).limit(limit).all()
    
    return {"employees": employees, "total": total}


@router.post("/{employee_id}/activate")
async def activate_inactive_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:update")),
):
    """Move an inactive employee back to the active Master Profiles table."""
    employee = db.query(EmployeeInactive).filter(EmployeeInactive.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Extract data for transfer
    data = {}
    
    # List of common fields to copy directly
    common_fields = [
        "fss_no", "name", "father_name", "status", "cnic", "mobile_no", "district",
        "serial_no", "rank", "salary", "unit", "service_rank", "blood_group",
        "status2", "unit2", "rank2", "dob", "cnic_expiry", "documents_held",
        "documents_handed_over_to", "photo_on_doc", "eobi_no", "home_contact",
        "verified_by_sho", "verified_by_khidmat_markaz", "domicile", "verified_by_ssp",
        "enrolled", "re_enrolled", "village", "post_office", "thana", "tehsil",
        "duty_location", "police_trg_ltr_date", "vaccination_cert", "vol_no",
        "payments", "category", "designation", "allocation_status", "bank_accounts",
        "avatar_url", "cnic_attachment", "domicile_attachment", "sho_verified_attachment",
        "ssp_verified_attachment", "khidmat_verified_attachment", "police_trg_attachment",
        "photo_on_doc_attachment", "served_in_attachment", "vaccination_attachment",
        "height", "education", "medical_category", "medical_discharge_cause",
        "nok_name", "nok_relationship", "sons_count", "daughters_count",
        "brothers_count", "sisters_count", "interviewed_by", "introduced_by",
        "enrolled_as", "served_in", "experience_security", "deployment_details",
        "discharge_cause", "orig_docs_received"
    ]
    
    for field in common_fields:
        if hasattr(employee, field):
            data[field] = getattr(employee, field)
            
    # If enrolled was set in EmployeeInactive as 'doe', restore it if 'enrolled' is empty
    if not data.get("enrolled") and hasattr(employee, "doe"):
        data["enrolled"] = employee.doe
        
    active_emp = Employee2(**data)
    db.add(active_emp)
    db.delete(employee)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to activate employee: {str(e)}")
        
    return {"message": "Employee moved to master profiles successfully"}


@router.post("/import-local")
async def import_from_local_file(
    file_path: str = "C:\\Users\\ahmed\\Desktop\\newfolder\\erp\\inactive.json",
    db: Session = Depends(get_db)
):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            # The file is semicolon separated as seen in view_file
            reader = csv.DictReader(f, delimiter=';')
            
            # Skip the first row if it's A;B;C...
            # The reader already uses the first row as headers, but the first row in the file is A;B;C
            # The second row is FSS #;Name;...
            # DictReader will use A, B, C... as keys if we don't handle it.
            
            # Let's re-read and handle the headers manually based on what we saw
            f.seek(0)
            lines = f.readlines()
            if not lines:
                return {"message": "Empty file"}
                
            # Line 0: "A";"B";...
            # Line 1: "FSS #";"Name";...
            # Line 2: ;;;;;"Number";... (Seems like some sub-headers or empty)
            # Data starts from Line 3 (index 3)
            
            headers = [h.strip('"') for h in lines[1].strip().split(';')]
            
            # Mapping from header to model field
            mapping = {
                "FSS #": "fss_no",
                "Name": "name",
                "Father's Name": "father_name",
                "Status": "status",
                "CNIC #": "cnic",
                "EOBI ": "eobi_no",
                "Mob #": "mobile_no",
                "Distt": "district",
                "DOE": "doe",
                "DOD": "dod",
                "Cuase of Disch": "cause_of_discharge",
                "Police Verification": "police_verification",
                "Notice Fine": "notice_fine",
                "Uniform Fine": "uniform_fine",
                "Police Trg": "police_trg",
                "Clo Fine": "clo_fine",
                "Vol": "vol_no"
            }
            
            count = 0
            for i in range(3, len(lines)):
                vals = [v.strip().strip('"') for v in lines[i].strip().split(';')]
                if not vals or not any(vals):
                    continue
                
                data = {}
                for idx, val in enumerate(vals):
                    if idx < len(headers):
                        h = headers[idx]
                        field = mapping.get(h)
                        if field:
                            if field in ["doe", "dod"]:
                                data[field] = _excel_date_to_str(val)
                            else:
                                data[field] = val if val else None
                
                if not data.get("name"):
                    continue
                    
                # Basic check if already exists by fss_no and name
                existing = db.query(EmployeeInactive).filter(
                    EmployeeInactive.name == data["name"],
                    EmployeeInactive.fss_no == data.get("fss_no")
                ).first()
                
                if not existing:
                    db.add(EmployeeInactive(**data))
                    count += 1
            
            db.commit()
            return {"message": f"Successfully imported {count} employees"}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
