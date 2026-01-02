"""Employee2 API routes."""

import json
import os
import re
import uuid
import io
from datetime import datetime, date
from calendar import monthrange
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.api.dependencies import require_permission
from app.models.payroll_sheet_entry import PayrollSheetEntry
from app.models.payroll_payment_status import PayrollPaymentStatus
from app.models.employee2 import Employee2
from app.schemas.employee2 import (
    Employee2 as Employee2Schema,
    Employee2Create,
    Employee2Update,
    Employee2List,
)
from app.models.employee_inactive import EmployeeInactive

class PendingDeactivationRequest(BaseModel):
    deactivation_date: str

router = APIRouter(dependencies=[Depends(require_permission("employees:view"))])

# Upload directory for employee2 files
UPLOAD_DIR = Path(settings.UPLOADS_DIR) / "employees2"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_model=Employee2List)
async def list_employees2(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    with_total: bool = True,
    db: Session = Depends(get_db),
):
    """Return a paginated list of Employee2 records."""
    query = db.query(Employee2)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Employee2.name.ilike(search_term))
            | (Employee2.fss_no.ilike(search_term))
            | (Employee2.cnic.ilike(search_term))
            | (Employee2.mobile_no.ilike(search_term))
            | (Employee2.serial_no.ilike(search_term))
        )
    
    if category:
        query = query.filter(Employee2.category == category)
    
    if status:
        query = query.filter(Employee2.status == status)
    
    total = query.count() if with_total else 0
    employees = query.offset(skip).limit(limit).all()
    
    return Employee2List(employees=employees, total=total)


@router.get("/categories")
async def list_categories(db: Session = Depends(get_db)):
    """Get distinct categories."""
    rows = db.query(Employee2.category).distinct().filter(Employee2.category.isnot(None)).all()
    return [r[0] for r in rows if r[0] and str(r[0]).strip()]


@router.get("/statuses")
async def list_statuses(db: Session = Depends(get_db)):
    """Get distinct statuses."""
    rows = db.query(Employee2.status).distinct().filter(Employee2.status.isnot(None)).all()
    return [r[0] for r in rows if r[0] and str(r[0]).strip()]


@router.post("/", response_model=Employee2Schema)
async def create_employee2(
    employee: Employee2Create,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:create")),
):
    """Create a new Employee2 record."""

    def _next_serial_no() -> str:
        # serial_no is stored as text; we only consider purely numeric values.
        # This keeps behavior consistent across SQLite/Postgres.
        max_n = 0
        for (s,) in db.query(Employee2.serial_no).filter(Employee2.serial_no.isnot(None)).all():
            if s is None:
                continue
            ss = str(s).strip()
            if not ss:
                continue
            if re.fullmatch(r"\d+", ss):
                try:
                    max_n = max(max_n, int(ss))
                except Exception:
                    continue
        return str(max_n + 1)

    def _resync_employee2_id_sequence() -> None:
        # Postgres-only: ensure the sequence is >= max(id) so inserts don't reuse existing PKs.
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('employees2','id'), "
                "COALESCE((SELECT MAX(id) FROM employees2), 1), true)"
            )
        )

    payload = employee.model_dump(exclude={"id"}, exclude_unset=True)

    # Ensure serial_no stays sequential: if missing/blank, set to max+1.
    # This makes Payroll2 '#' ordering stable and ensures new employees get the last number.
    serial_no = str(payload.get("serial_no") or "").strip()
    if not serial_no:
        payload["serial_no"] = _next_serial_no()

    db_employee = Employee2(**payload)
    db.add(db_employee)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # If the PK sequence is out-of-sync, repair and retry once.
        msg = str(getattr(e, "orig", e))
        if "employees2_pkey" in msg or "duplicate key value" in msg:
            _resync_employee2_id_sequence()
            db_employee = Employee2(**payload)
            db.add(db_employee)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Could not create employee (duplicate primary key).",
                )
        else:
            raise HTTPException(status_code=400, detail="Could not create employee.")

    db.refresh(db_employee)
    
    # Automatically create payroll entry for current month
    _create_payroll_entry_for_new_employee(db_employee, db)
    
    return db_employee


def _create_payroll_entry_for_new_employee(employee: Employee2, db: Session):
    """Automatically create payroll entry for new employee for current month."""
    try:
        # Get current month date range
        today = date.today()
        year = today.year
        month = today.month
        
        # Calculate first and last day of current month
        last_day = monthrange(year, month)[1]
        from_date = date(year, month, 1)
        to_date = date(year, month, last_day)
        
        # Check if payroll entry already exists for this employee and period
        existing_entry = db.query(PayrollSheetEntry).filter(
            PayrollSheetEntry.employee_db_id == employee.id,
            PayrollSheetEntry.from_date == from_date,
            PayrollSheetEntry.to_date == to_date
        ).first()
        
        if not existing_entry:
            # Create new payroll entry
            payroll_entry = PayrollSheetEntry(
                employee_db_id=employee.id,
                from_date=from_date,
                to_date=to_date,
                pre_days_override=0,  # Will be calculated from attendance
                cur_days_override=0,  # Will be calculated from attendance
                leave_encashment_days=0,
                allow_other=0.0,
                eobi=0.0,
                tax=0.0,
                fine_adv_extra=0.0,
                remarks="Auto-created for new employee",
                bank_cash="Bank"  # Default payment method
            )
            
            db.add(payroll_entry)
            
            # Create payment status entry
            month_str = f"{year:04d}-{month:02d}"
            employee_id = employee.fss_no or employee.serial_no or str(employee.id)
            
            existing_payment_status = db.query(PayrollPaymentStatus).filter(
                PayrollPaymentStatus.month == month_str,
                PayrollPaymentStatus.employee_id == employee_id
            ).first()
            
            if not existing_payment_status:
                payment_status = PayrollPaymentStatus(
                    month=month_str,
                    employee_id=employee_id,
                    status="unpaid"
                )
                db.add(payment_status)
            
            db.commit()
            
    except Exception as e:
        # Log error but don't fail employee creation
        print(f"Error creating payroll entry for employee {employee.id}: {e}")
        db.rollback()


@router.post("/import-json", dependencies=[Depends(require_permission("employees:create"))])
async def import_from_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import Employee2 records from JSON file."""
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")
    
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of records")
    
    created = 0
    skipped = 0
    errors = []
    current_category = None
    
    # Skip header rows (first 2 rows typically)
    for idx, row in enumerate(data):
        try:
            # Get values with fallback
            a_val = str(row.get("A", "") or "").strip()
            b_val = str(row.get("B", "") or "").strip()
            c_val = str(row.get("C", "") or "").strip()
            d_val = str(row.get("D", "") or "").strip()
            
            # Skip header row
            if a_val == "#" or d_val == "Name":
                continue
            
            # Skip empty number row
            if a_val == "" and b_val == "" and c_val == "" and d_val == "":
                continue
            
            # Check if this is a category row (no numeric serial, has text in A)
            if a_val and not a_val.isdigit() and not d_val:
                current_category = a_val
                continue
            
            # Skip if no name
            if not d_val:
                skipped += 1
                continue
            
            employee_data = {
                "serial_no": a_val or None,
                "fss_no": b_val or None,
                "rank": c_val or None,
                "name": d_val,
                "father_name": str(row.get("E", "") or "").strip() or None,
                "salary": str(row.get("F", "") or "").strip() or None,
                "status": str(row.get("G", "") or "").strip() or None,
                "unit": str(row.get("H", "") or "").strip() or None,
                "service_rank": str(row.get("I", "") or "").strip() or None,
                "blood_group": str(row.get("J", "") or "").strip() or None,
                "status2": str(row.get("K", "") or "").strip() or None,
                "unit2": str(row.get("L", "") or "").strip() or None,
                "rank2": str(row.get("M", "") or "").strip() or None,
                "cnic": str(row.get("N", "") or "").strip() or None,
                "dob": str(row.get("O", "") or "").strip() or None,
                "cnic_expiry": str(row.get("P", "") or "").strip() or None,
                "documents_held": str(row.get("Q", "") or "").strip() or None,
                "documents_handed_over_to": str(row.get("R", "") or "").strip() or None,
                "photo_on_doc": str(row.get("S", "") or "").strip() or None,
                "eobi_no": str(row.get("T", "") or "").strip() or None,
                "insurance": str(row.get("W", "") or "").strip() or None,
                "social_security": str(row.get("X", "") or "").strip() or None,
                "mobile_no": str(row.get("Y", "") or "").strip() or None,
                "home_contact": str(row.get("Z", "") or "").strip() or None,
                "verified_by_sho": str(row.get("AA", "") or "").strip() or None,
                "verified_by_khidmat_markaz": str(row.get("AB", "") or "").strip() or None,
                "domicile": str(row.get("AC", "") or "").strip() or None,
                "verified_by_ssp": str(row.get("AD", "") or "").strip() or None,
                "enrolled": str(row.get("AE", "") or "").strip() or None,
                "re_enrolled": str(row.get("AF", "") or "").strip() or None,
                "village": str(row.get("AG", "") or "").strip() or None,
                "post_office": str(row.get("AH", "") or "").strip() or None,
                "thana": str(row.get("AI", "") or "").strip() or None,
                "tehsil": str(row.get("AJ", "") or "").strip() or None,
                "district": str(row.get("AK", "") or "").strip() or None,
                "duty_location": str(row.get("AL", "") or "").strip() or None,
                "police_trg_ltr_date": str(row.get("AM", "") or "").strip() or None,
                "vaccination_cert": str(row.get("AN", "") or "").strip() or None,
                "vol_no": str(row.get("AO", "") or "").strip() or None,
                "payments": str(row.get("AP", "") or "").strip() or None,
                "category": current_category,
            }
            
            db_employee = Employee2(**employee_data)
            db.add(db_employee)
            created += 1
            
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")
    
    db.commit()
    
    return {
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],  # Limit errors returned
        "total_rows": len(data),
    }


@router.get("/{employee_id}", response_model=Employee2Schema)
async def get_employee2(employee_id: int, db: Session = Depends(get_db)):
    """Get a single Employee2 by ID."""
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/{employee_id}", response_model=Employee2Schema)
async def update_employee2(
    employee_id: int,
    employee_update: Employee2Update,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:update")),
):
    """Update an Employee2 record."""
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)
    
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}")
async def delete_employee2(
    employee_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("employees:delete")),
):
    """Delete an Employee2 record."""
    print(f"DEBUG: Delete attempt by {getattr(user, 'username', 'unknown')} on ID {employee_id}")
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    db.delete(employee)
    db.commit()
    return {"message": "Employee deleted successfully"}


@router.delete("/")
async def delete_all_employees2(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:delete")),
):
    """Delete all Employee2 records (for re-import)."""
    count = db.query(Employee2).delete()
    db.commit()
    return {"message": f"Deleted {count} employees"}


@router.post("/{employee_id}/deactivate")
async def deactivate_employee2(
    employee_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:update")),
):
    """Move an active employee to the inactive table."""
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Extract data for transfer
    # We want to match EmployeeInactive fields as much as possible
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
            
    # Set Date of Discharge to today
    data["dod"] = datetime.now().strftime("%Y-%m-%d")
    # Date of Enrollment map
    data["doe"] = employee.enrolled
    
    inactive_emp = EmployeeInactive(**data)
    db.add(inactive_emp)
    db.delete(employee)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to move employee: {str(e)}")
        
    return {"message": "Employee moved to inactive section successfully"}


@router.post("/{employee_id}/pending-deactivate")
async def create_pending_deactivation(
    employee_id: int,
    data: PendingDeactivationRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:update")),
):
    """Submit an employee to pending deactivation queue"""
    # Forward to HR module
    from app.api.routes import hr as hr_routes
    
    # Get employee
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Import HR module functions
    from app.api.routes.hr import PendingDeactivationResponse
    
    # Check if already pending
    existing = next((p for p in hr_routes._pending_deactivations if p["employee_db_id"] == employee_id), None)
    if existing:
        raise HTTPException(status_code=400, detail="Employee already has a pending deactivation")
    
    # Calculate all required data
    inventory_items = hr_routes._get_employee_inventory(db, employee)
    attendance_summary = hr_routes._calculate_attendance_summary(db, employee, data.deactivation_date)
    salary_calculation = hr_routes._calculate_salary(db, employee, attendance_summary)
    settlement = hr_routes._calculate_settlement(inventory_items, salary_calculation)
    employee_identifier = (
        getattr(employee, "fss_no", None)
        or getattr(employee, "serial_no", None)
        or str(getattr(employee, "id", ""))
    )

    bank_name = None
    bank_account_number = None
    try:
        raw_bank_accounts = getattr(employee, "bank_accounts", None)
        if raw_bank_accounts:
            parsed = json.loads(raw_bank_accounts)
            primary = None
            if isinstance(parsed, list) and parsed:
                primary = parsed[0]
            elif isinstance(parsed, dict):
                primary = parsed

            if isinstance(primary, dict):
                bank_name = primary.get("bank_name") or primary.get("bank") or primary.get("name")
                bank_account_number = (
                    primary.get("bank_account_number")
                    or primary.get("account_number")
                    or primary.get("accountNo")
                    or primary.get("account")
                )
    except Exception:
        bank_name = None
        bank_account_number = None
    
    # Create pending deactivation record
    pending = {
        "id": hr_routes._next_id,
        "employee_db_id": employee.id,
        "employee_id": employee_identifier or "",
        "name": employee.name or "",
        "serial_no": employee.serial_no,
        "fss_no": employee.fss_no,
        "rank": employee.rank,
        "category": employee.category,
        "unit": employee.unit,
        "cnic": employee.cnic,
        "mobile_no": employee.mobile_no,
        "bank_name": bank_name,
        "bank_account_number": bank_account_number,
        "base_salary": int(employee.salary or 0),
        "deactivation_date": data.deactivation_date,
        "created_at": datetime.now().isoformat(),
        "inventory_items": [item.dict() for item in inventory_items],
        "attendance_summary": attendance_summary.dict(),
        "salary_calculation": salary_calculation.dict(),
        "settlement": settlement.dict()
    }
    
    hr_routes._pending_deactivations.append(pending)
    hr_routes._next_id += 1
    
    return PendingDeactivationResponse(**pending)


@router.post("/{employee_id}/upload/{field_type}")
async def upload_employee_file(
    employee_id: int,
    field_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(require_permission("employees:update")),
):
    """Upload a file for an employee (avatar, cnic, domicile, etc.)."""
    # Validate field type
    valid_fields = [
        "avatar", "cnic", "domicile", "sho_verified", 
        "ssp_verified", "khidmat_verified", "police_trg",
        "photo_on_doc", "served_in", "vaccination",
        "personal_signature", "employment_agreement",
        "recording_officer_signature",
        "experience_security",
        "education",
        "nok_cnic",
        "other_documents",
        "fingerprint_thumb", "fingerprint_index", "fingerprint_middle", 
        "fingerprint_ring", "fingerprint_pinky"
    ]
    if field_type not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field type. Must be one of: {valid_fields}")
    
    # Get employee
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        new_filename = f"emp{employee_id}_{field_type}_{timestamp}_{unique_id}{file_ext}"
        
        # Save file
        file_path = UPLOAD_DIR / new_filename
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Update employee record
        file_url = f"/uploads/employees2/{new_filename}"
        field_name = f"{field_type}_attachment" if field_type != "avatar" else "avatar_url"
        setattr(employee, field_name, file_url)
        db.commit()
        db.refresh(employee)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "url": file_url,
                "field": field_name,
                "filename": new_filename,
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


class EmployeePDF(FPDF):
    """Custom PDF class for employee export."""
    
    def __init__(self, employee_name: str):
        super().__init__()
        self.employee_name = employee_name
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.set_fill_color(255, 255, 255)
        self.rect(0, 0, 210, 34, 'F')

        logo_candidates = [
            PROJECT_ROOT / "Logo-removebg-preview.png",
            PROJECT_ROOT / "logo.png",
            PROJECT_ROOT / "frontend-next" / "public" / "logo.png",
            PROJECT_ROOT / "frontend-next" / "public" / "logo.svg",
        ]
        logo_path = None
        for p in logo_candidates:
            try:
                if p.exists() and p.is_file():
                    logo_path = p
                    break
            except Exception:
                continue

        if logo_path and str(logo_path).lower().endswith(".svg"):
            logo_path = None

        if logo_path:
            try:
                logo_w = 22
                logo_x = (210 - logo_w) / 2
                self.image(str(logo_path), x=logo_x, y=4, w=logo_w)
            except Exception:
                pass

        self.set_y(20)
        self.set_text_color(15, 23, 42)
        self.set_font("Arial", "B", 12)
        self.cell(0, 6, "FLASH TECH ERP", 0, 1, "C")
        self.set_font("Arial", "", 10)
        self.set_text_color(55, 65, 81)
        self.cell(0, 5, "Employee Profile", 0, 1, "C")

        self.set_draw_color(229, 231, 235)
        self.line(12, 34, 198, 34)
        self.set_text_color(0, 0, 0)
        self.ln(8)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Page {self.page_no()}", 0, 0, "C")
        self.set_text_color(0, 0, 0)
    
    def section_title(self, title: str):
        self.ln(3)
        self.set_font("Arial", "B", 11)
        self.set_fill_color(248, 250, 252)
        self.set_draw_color(229, 231, 235)
        self.cell(0, 8, "  " + title, 1, 1, "L", True)
        self.ln(2)
    
    def add_table_row(self, data: list, widths: list, is_header: bool = False):
        """Add a table row with borders."""
        if is_header:
            self.set_font("Arial", "B", 9)
            self.set_fill_color(245, 245, 245)
        else:
            self.set_font("Arial", "", 9)
        
        h = 7
        for i, (text, w) in enumerate(zip(data, widths)):
            self.cell(w, h, str(text) if text else "-", 1, 0, "L", is_header)
        self.ln()
    
    def info_box(self, label: str, value: str, w: int = 63):
        """Create a labeled info box."""
        self.set_font("Arial", "B", 8)
        self.set_text_color(100, 100, 100)
        self.cell(w, 5, label, 0, 0, "L")
        self.set_font("Arial", "", 9)
        self.set_text_color(0, 0, 0)
        self.set_x(self.get_x() - w)
        self.set_y(self.get_y() + 4)
        self.cell(w, 6, str(value) if value else "-", 0, 0, "L")
        self.set_y(self.get_y() - 4)


@router.get("/{employee_id}/export-pdf")
async def export_employee_pdf(
    employee_id: int,
    db: Session = Depends(get_db),
):
    """Export employee details as PDF with updated layout including all new fields."""
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    pdf = EmployeePDF(employee.name or "Unknown")
    pdf.add_page()

    top_y = pdf.get_y()
    card_y = max(top_y, 42)
    
    # Profile picture
    avatar_loaded = False
    if employee.avatar_url:
        avatar_path = PROJECT_ROOT / employee.avatar_url.lstrip("/")
        if avatar_path.exists():
            try:
                pdf.set_draw_color(229, 231, 235)
                pdf.ellipse(15, card_y + 4, 30, 30, 'D')
                pdf.image(str(avatar_path), x=16, y=card_y + 5, w=28, h=28)
                avatar_loaded = True
            except:
                pass
    
    if not avatar_loaded:
        # Draw placeholder circle
        pdf.set_fill_color(200, 200, 200)
        pdf.ellipse(15, card_y + 4, 30, 30, 'F')
        pdf.set_font("Arial", "B", 20)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(15, card_y + 11)
        initials = "".join([n[0].upper() for n in (employee.name or "?").split()[:2]])
        pdf.cell(30, 10, initials, 0, 0, "C")
        pdf.set_text_color(0, 0, 0)
    
    # Name and basic info next to photo
    pdf.set_xy(50, card_y + 4)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, employee.name or "-", 0, 1)
    
    pdf.set_x(50)
    pdf.set_font("Arial", "", 10)
    info_parts = []
    if employee.category:
        info_parts.append(employee.category)
    if employee.rank:
        info_parts.append(employee.rank)
    if employee.fss_no:
        info_parts.append(f"FSS #{employee.fss_no}")
    pdf.cell(0, 6, " | ".join(info_parts) if info_parts else "-", 0, 1)
    
    pdf.set_x(50)
    info_parts2 = []
    if employee.allocation_status:
        info_parts.append(employee.allocation_status)
    if employee.salary:
        info_parts.append(f"Salary {employee.salary}")
    if employee.blood_group:
        info_parts.append(f"Blood {employee.blood_group}")
    pdf.cell(0, 6, " | ".join(info_parts2) if info_parts2 else "-", 0, 1)
    
    # Status badge
    if employee.allocation_status:
        pdf.set_x(50)
        if employee.allocation_status == "Free":
            pdf.set_fill_color(82, 196, 26)
        else:
            pdf.set_fill_color(250, 173, 20)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(25, 6, employee.allocation_status, 0, 0, "C", True)
        pdf.set_text_color(0, 0, 0)

    pdf.set_draw_color(229, 231, 235)
    pdf.line(10, card_y + 38, 200, card_y + 38)

    pdf.set_y(card_y + 46)
    
    # Executive Summary Section
    pdf.section_title("Executive Summary")
    
    # Profile image on the right
    if employee.avatar_url:
        avatar_path = PROJECT_ROOT / employee.avatar_url.lstrip("/")
        if avatar_path.exists():
            try:
                pdf.set_x(150)
                pdf.set_draw_color(229, 231, 235)
                pdf.rect(150, pdf.get_y(), 50, 60, 'D')
                pdf.image(str(avatar_path), x=151, y=pdf.get_y() + 1, w=48, h=58)
                pdf.set_y(pdf.get_y() + 65)
            except:
                pass
    
    # Executive Summary Info (left side)
    pdf.set_x(10)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(35, 6, "Interviewed By", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 6, str(employee.interviewed_by) if employee.interviewed_by else "-", 0, 1)
    
    pdf.set_x(10)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(35, 6, "Introduced By", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 6, str(employee.introduced_by) if employee.introduced_by else "-", 0, 1)
    
    pdf.ln(5)
    
    # Salary, Status, Unit, Service Rank in two columns
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "Salary", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 6, str(employee.salary) if employee.salary else "-", 0, 0)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "Status", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 6, str(employee.status) if employee.status else "-", 0, 1)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "Unit", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 6, str(employee.unit) if employee.unit else "-", 0, 0)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "Service Rank", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(40, 6, str(employee.service_rank) if employee.service_rank else "-", 0, 1)
    
    # Original Documents Held
    pdf.set_x(10)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(60, 6, "Original Documents Held", 0, 1)
    pdf.set_x(10)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, str(employee.documents_held) if employee.documents_held else "-", 0, 1)
    
    pdf.ln(3)
    
    # Enrolled and Re-Enrolled
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(35, 6, "Enrolled On", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 6, str(employee.enrolled) if employee.enrolled else "-", 0, 0)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(35, 6, "Re-Enrolled", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 6, str(employee.re_enrolled) if employee.re_enrolled else "-", 0, 1)
    
    pdf.ln(5)
    
    # Bio Data Section
    pdf.section_title("Bio Data")
    
    bio_data = [
        ("Father's Name", employee.father_name),
        ("CNIC Number", employee.cnic),
        ("DOB", employee.dob),
        ("CNIC Expiry", employee.cnic_expiry),
        ("Education", employee.education),
        ("Medical Details", employee.medical_details),
        ("Medical Category", employee.medical_category),
        ("Mobile Number", employee.mobile_no),
    ]
    
    for label, value in bio_data:
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(45, 6, label, 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        if label in ["Medical Details", "Original Documents Held"]:
            pdf.multi_cell(0, 6, str(value) if value else "-", 0, 1)
        else:
            pdf.cell(0, 6, str(value) if value else "-", 0, 1)
    
    # Permanent Address
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, "Permanent Address", 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    permanent_address = [
        ("Village", employee.village),
        ("Post Office", employee.post_office),
        ("Thana", employee.thana),
        ("Tehsil", employee.tehsil),
        ("District", employee.district),
        ("Duty Location", employee.duty_location),
    ]
    
    for label, value in permanent_address:
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 5, label, 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, str(value) if value else "-", 0, 1)
    
    pdf.ln(3)
    
    # Temporary Address
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 8, "Temporary Address", 0, 1)
    pdf.set_text_color(0, 0, 0)
    
    temp_address = [
        ("Village", employee.temp_village),
        ("Post Office", employee.temp_post_office),
        ("Thana", employee.temp_thana),
        ("Tehsil", employee.temp_tehsil),
        ("District", employee.temp_district),
        ("City", employee.temp_city),
        ("Phone", employee.temp_phone),
    ]
    
    for label, value in temp_address:
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 5, label, 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, str(value) if value else "-", 0, 1)
    
    # Temporary address details
    if employee.temp_address_details:
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(30, 5, "Address Details", 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, str(employee.temp_address_details), 0, 1)
    
    pdf.ln(3)
    
    # Family & Health Section
    pdf.section_title("Family & Health")
    
    # Next of Kin
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(35, 6, "Next of Kin", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    nok_info = f"{employee.nok_name or '-'} ({employee.nok_relationship or '-'})"
    pdf.cell(0, 6, nok_info, 0, 1)
    
    pdf.ln(3)
    
    # Family counts in two columns
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "SONS", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(25, 6, str(employee.sons_count) if employee.sons_count else "N/a", 0, 0)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "DTRS", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(25, 6, str(employee.daughters_count) if employee.daughters_count else "N/A", 0, 1)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "BROS", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(25, 6, str(employee.brothers_count) if employee.brothers_count else "-", 0, 0)
    
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(25, 6, "SISTERS", 0, 0)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(25, 6, str(employee.sisters_count) if employee.sisters_count else "-", 0, 1)
    
    pdf.ln(5)
    
    # Verifications & Background Section
    pdf.section_title("Verifications & Background")
    
    verification_data = [
        ("SHO Verified", employee.verified_by_sho),
        ("SSP Verified", employee.verified_by_ssp),
        ("Khidmat Markaz", employee.verified_by_khidmat_markaz),
        ("Police Training", employee.police_trg_ltr_date),
    ]
    
    for i in range(0, len(verification_data), 2):
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(50, 6, verification_data[i][0], 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(30, 6, str(verification_data[i][1]) if verification_data[i][1] else "-", 0, 0)
        
        if i + 1 < len(verification_data):
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(50, 6, verification_data[i+1][0], 0, 0)
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(30, 6, str(verification_data[i+1][1]) if verification_data[i+1][1] else "-", 0, 1)
        else:
            pdf.ln()
    
    pdf.ln(5)
    
    # Fingerprint Attachments Section
    fingerprint_attachments = [
        ("Thumb Print", employee.fingerprint_thumb_attachment),
        ("Index Finger", employee.fingerprint_index_attachment),
        ("Middle Finger", employee.fingerprint_middle_attachment),
        ("Ring Finger", employee.fingerprint_ring_attachment),
        ("Pinky Finger", employee.fingerprint_pinky_attachment),
    ]
    
    has_fingerprints = any(att[1] for att in fingerprint_attachments)
    if has_fingerprints:
        pdf.section_title("Fingerprint Attachments")
        
        for label, url in fingerprint_attachments:
            if url:
                file_path = PROJECT_ROOT / url.lstrip("/")
                if file_path.exists():
                    ext = file_path.suffix.lower()
                    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
                        try:
                            if pdf.get_y() > 200:
                                pdf.add_page()
                                pdf.set_y(30)
                            
                            pdf.set_font("Arial", "B", 9)
                            pdf.set_fill_color(100, 100, 100)
                            pdf.set_text_color(255, 255, 255)
                            pdf.cell(50, 6, "  " + label, 0, 1, "L", True)
                            pdf.set_text_color(0, 0, 0)
                            pdf.ln(2)
                            
                            # Add fingerprint image
                            pdf.image(str(file_path), x=20, w=170)
                            pdf.ln(8)
                        except:
                            pdf.set_font("Arial", "I", 9)
                            pdf.cell(0, 6, f"{label}: [Image could not be loaded]", 0, 1)
                            pdf.ln(2)
                    else:
                        pdf.set_font("Arial", "B", 9)
                        pdf.cell(0, 6, f"{label}: [{ext.upper()} File]", 0, 1)
                        pdf.ln(2)
                else:
                    pdf.set_font("Arial", "I", 9)
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(0, 6, f"{label}: [File not found]", 0, 1)
                    pdf.ln(2)
            else:
                pdf.set_font("Arial", "I", 9)
                pdf.set_text_color(200, 200, 200)
                pdf.cell(0, 6, f"{label}: [Not uploaded]", 0, 1)
                pdf.ln(2)
        
        pdf.ln(3)
    
    # Signature Section
    if employee.personal_signature_attachment:
        pdf.section_title("Signature")
        signature_path = PROJECT_ROOT / employee.personal_signature_attachment.lstrip("/")
        if signature_path.exists():
            try:
                pdf.set_font("Arial", "B", 9)
                pdf.set_fill_color(100, 100, 100)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(50, 6, "  Personal Signature", 0, 1, "L", True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)
                
                # Add signature image
                pdf.image(str(signature_path), x=50, w=100)
                pdf.ln(8)
            except:
                pdf.set_font("Arial", "I", 9)
                pdf.cell(0, 6, "Personal Signature: [Image could not be loaded]", 0, 1)
                pdf.ln(2)
        else:
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 6, "Personal Signature: [File not found]", 0, 1)
            pdf.ln(2)
        
        pdf.ln(3)
    
    # All Other Attachments
    other_attachments = [
        ("CNIC", employee.cnic_attachment),
        ("Domicile", employee.domicile_attachment),
        ("SHO Verification", employee.sho_verified_attachment),
        ("SSP Verification", employee.ssp_verified_attachment),
        ("Khidmat Verification", employee.khidmat_verified_attachment),
        ("Police Training", employee.police_trg_attachment),
        ("Photo on Document", employee.photo_on_doc_attachment),
        ("Employment Agreement", employee.employment_agreement_attachment),
        ("Served In Certificate", employee.served_in_attachment),
        ("Vaccination", employee.vaccination_attachment),
    ]
    
    has_other_attachments = any(att[1] for att in other_attachments)
    if has_other_attachments:
        pdf.section_title("All Attachments")
        
        for label, url in other_attachments:
            if url:
                file_path = PROJECT_ROOT / url.lstrip("/")
                if file_path.exists():
                    ext = file_path.suffix.lower()
                    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
                        try:
                            if pdf.get_y() > 200:
                                pdf.add_page()
                                pdf.set_y(30)
                            
                            pdf.set_font("Arial", "B", 9)
                            pdf.set_fill_color(24, 144, 255)
                            pdf.set_text_color(255, 255, 255)
                            pdf.cell(60, 7, "  " + label, 0, 1, "L", True)
                            pdf.set_text_color(0, 0, 0)
                            pdf.ln(2)
                            
                            # Add image
                            pdf.image(str(file_path), x=15, w=180)
                            pdf.ln(8)
                        except:
                            pdf.set_font("Arial", "I", 9)
                            pdf.cell(0, 6, f"{label}: [Image could not be loaded]", 0, 1)
                            pdf.ln(2)
                    elif ext == ".pdf":
                        pdf.set_font("Arial", "B", 9)
                        pdf.set_fill_color(250, 140, 22)
                        pdf.set_text_color(255, 255, 255)
                        pdf.cell(0, 8, "  " + label + " (PDF Document)", 0, 1, "L", True)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font("Arial", "", 9)
                        pdf.cell(0, 6, f"File: {os.path.basename(url)}", 0, 1)
                        pdf.ln(3)
                    else:
                        pdf.set_font("Arial", "B", 9)
                        pdf.set_fill_color(150, 150, 150)
                        pdf.set_text_color(255, 255, 255)
                        pdf.cell(0, 8, "  " + label + f" ({ext.upper()} File)", 0, 1, "L", True)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font("Arial", "", 9)
                        pdf.cell(0, 6, f"File: {os.path.basename(url)}", 0, 1)
                        pdf.ln(3)
                else:
                    pdf.set_font("Arial", "I", 9)
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(0, 6, f"{label}: [File not found]", 0, 1)
                    pdf.ln(2)
            else:
                pdf.set_font("Arial", "I", 9)
                pdf.set_text_color(200, 200, 200)
                pdf.cell(0, 6, f"{label}: [Not uploaded]", 0, 1)
                pdf.ln(2)
    
    # Generate PDF
    pdf_bytes = pdf.output(dest="S").encode("latin-1") if isinstance(pdf.output(dest="S"), str) else pdf.output(dest="S")
    
    # Create filename
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in (employee.name or "employee"))
    filename = f"Employee_{employee.id}_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
