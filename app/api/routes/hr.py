from datetime import datetime
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.models.employee2 import Employee2
from app.models.employee_inactive import EmployeeInactive
from app.models.general_item import GeneralItem
from app.models.general_item_employee_balance import GeneralItemEmployeeBalance
from app.models.restricted_item import RestrictedItem
from app.models.restricted_item_employee_balance import RestrictedItemEmployeeBalance
from app.models.restricted_item_serial_unit import RestrictedItemSerialUnit

router = APIRouter(tags=["HR"])

# Pydantic models
class PendingDeactivationCreate(BaseModel):
    deactivation_date: str  # YYYY-MM-DD

class InventoryItem(BaseModel):
    item_name: str
    assigned_date: str
    condition: str
    value: Optional[int] = None

class AttendanceSummary(BaseModel):
    total_days: int
    present_days: int
    absent_days: int
    leave_days: int
    late_days: int
    from_date: str
    to_date: str

class Deductions(BaseModel):
    eobi: Optional[int] = 0
    tax: Optional[int] = 0
    advance: Optional[int] = 0
    fine: Optional[int] = 0

class SalaryCalculation(BaseModel):
    gross_salary: int
    deductions: Deductions
    net_payable: int

class Settlement(BaseModel):
    total_to_collect: int
    total_to_pay: int
    net_amount: int

class PendingDeactivationResponse(BaseModel):
    id: int
    employee_db_id: int
    employee_id: str
    name: str
    serial_no: Optional[str]
    fss_no: Optional[str]
    rank: Optional[str]
    category: Optional[str]
    unit: Optional[str]
    cnic: Optional[str]
    mobile_no: Optional[str]
    avatar_url: Optional[str] = None
    bank_name: Optional[str]
    bank_account_number: Optional[str]
    base_salary: Optional[int]
    deactivation_date: str
    created_at: str
    inventory_items: List[InventoryItem]
    attendance_summary: AttendanceSummary
    salary_calculation: SalaryCalculation
    settlement: Settlement

# In-memory storage for demo (replace with DB table in production)
_pending_deactivations: List[dict] = []
_next_id = 1

def _attendance_employee_key(employee: Employee2) -> str:
    # Attendance module uses AttendanceRecord.employee_id (string). In this ERP it is typically
    # fss_no/serial_no or as fallback the numeric DB id as string.
    return str(employee.fss_no or employee.serial_no or employee.id)


def _find_legacy_employee_id(db: Session, employee: Employee2) -> Optional[str]:
    """Inventory modules are keyed by legacy employees.employee_id.

    Try to map Employee2 -> Employee.
    """

    # 1) Match by CNIC (strongest)
    cnic = (employee.cnic or "").strip()
    if cnic:
        emp = db.query(Employee).filter(Employee.cnic == cnic).first()
        if emp:
            return str(emp.employee_id)

    # 2) Match by exact full name
    name = (employee.name or "").strip().lower()
    if name:
        # Employees store first_name/last_name
        candidates = db.query(Employee).all()
        for e in candidates:
            full = f"{(e.first_name or '').strip()} {(e.last_name or '').strip()}".strip().lower()
            if full and full == name:
                return str(e.employee_id)

    # 3) If fss_no/serial_no happen to be same as legacy employee_id
    for v in [employee.fss_no, employee.serial_no]:
        vv = (v or "").strip()
        if vv:
            emp = db.query(Employee).filter(Employee.employee_id == vv).first()
            if emp:
                return str(emp.employee_id)

    return None


def _get_employee_inventory(db: Session, employee: Employee2) -> List[InventoryItem]:
    """Fetch assigned inventory from real system tables."""

    legacy_id = _find_legacy_employee_id(db, employee)
    if not legacy_id:
        return []

    items: List[InventoryItem] = []

    # General inventory (quantity items)
    gen_rows = (
        db.query(GeneralItemEmployeeBalance, GeneralItem)
        .join(GeneralItem, GeneralItem.item_code == GeneralItemEmployeeBalance.item_code)
        .filter(GeneralItemEmployeeBalance.employee_id == legacy_id)
        .filter(GeneralItemEmployeeBalance.quantity_issued > 0)
        .all()
    )
    for bal, it in gen_rows:
        qty = float(bal.quantity_issued or 0.0)
        label = f"{it.name} x {qty:g} {it.unit_name}".strip()
        items.append(
            InventoryItem(
                item_name=label,
                assigned_date=(bal.created_at.isoformat() if getattr(bal, "created_at", None) else ""),
                condition="issued",
                value=None,
            )
        )

    # Restricted inventory (quantity items)
    res_qty_rows = (
        db.query(RestrictedItemEmployeeBalance, RestrictedItem)
        .join(RestrictedItem, RestrictedItem.item_code == RestrictedItemEmployeeBalance.item_code)
        .filter(RestrictedItemEmployeeBalance.employee_id == legacy_id)
        .filter(RestrictedItemEmployeeBalance.quantity_issued > 0)
        .all()
    )
    for bal, it in res_qty_rows:
        qty = float(bal.quantity_issued or 0.0)
        label = f"{it.name} x {qty:g} {it.unit_name}".strip()
        items.append(
            InventoryItem(
                item_name=label,
                assigned_date=(bal.created_at.isoformat() if getattr(bal, "created_at", None) else ""),
                condition="issued",
                value=None,
            )
        )

    # Restricted inventory (serial items)
    res_serials = (
        db.query(RestrictedItemSerialUnit, RestrictedItem)
        .join(RestrictedItem, RestrictedItem.item_code == RestrictedItemSerialUnit.item_code)
        .filter(RestrictedItemSerialUnit.issued_to_employee_id == legacy_id)
        .filter(RestrictedItemSerialUnit.status == "issued")
        .all()
    )
    for su, it in res_serials:
        label = f"{it.name} (SN: {su.serial_number})"
        items.append(
            InventoryItem(
                item_name=label,
                assigned_date=(su.created_at.isoformat() if getattr(su, "created_at", None) else ""),
                condition=str(su.status or "issued"),
                value=None,
            )
        )

    return items

def _calculate_attendance_summary(db: Session, employee: Employee2, deactivation_date: str) -> AttendanceSummary:
    """Calculate attendance summary up to deactivation date using attendance_records."""

    try:
        end_date = datetime.strptime(deactivation_date, "%Y-%m-%d").date()
    except Exception:
        end_date = datetime.now().date()

    # Prefer enrollment date if valid, otherwise fallback to first attendance record.
    start_date = None
    try:
        if employee.enrolled:
            start_date = datetime.strptime(str(employee.enrolled)[:10], "%Y-%m-%d").date()
    except Exception:
        start_date = None

    emp_key = _attendance_employee_key(employee)

    if start_date is None:
        first = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp_key)
            .order_by(AttendanceRecord.date.asc())
            .first()
        )
        if first:
            start_date = first.date
        else:
            start_date = end_date

    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.employee_id == emp_key)
        .filter(AttendanceRecord.date >= start_date)
        .filter(AttendanceRecord.date <= end_date)
        .all()
    )

    present_days = 0
    absent_days = 0
    leave_days = 0
    late_days = 0

    for r in records:
        st = str(r.status or "").strip().lower()
        if st == "present":
            present_days += 1
        elif st == "late":
            late_days += 1
            present_days += 1
        elif st == "absent":
            absent_days += 1
        elif st == "leave":
            leave_days += 1

    total_days = (end_date - start_date).days + 1

    return AttendanceSummary(
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        leave_days=leave_days,
        late_days=late_days,
        from_date=start_date.isoformat(),
        to_date=end_date.isoformat(),
    )

def _calculate_salary(db: Session, employee: Employee2, attendance: AttendanceSummary) -> SalaryCalculation:
    """Calculate salary from real attendance records.

    Notes:
    - Uses employee.salary as monthly base.
    - Payable days = present (includes late) + leave.
    - Deductions are taken from attendance_records late_deduction + fine_amount.
    """

    base_salary = 0
    try:
        base_salary = int(float(employee.salary or 0))
    except Exception:
        base_salary = 0

    from_date = datetime.strptime(attendance.from_date, "%Y-%m-%d").date() if attendance.from_date else None
    to_date = datetime.strptime(attendance.to_date, "%Y-%m-%d").date() if attendance.to_date else None

    emp_key = _attendance_employee_key(employee)

    fine_total = 0.0
    late_ded_total = 0.0
    ot_pay_total = 0.0
    paid_leave_days = 0
    unpaid_leave_days = 0

    if from_date and to_date:
        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.employee_id == emp_key)
            .filter(AttendanceRecord.date >= from_date)
            .filter(AttendanceRecord.date <= to_date)
            .all()
        )
        for r in records:
            fine_total += float(r.fine_amount or 0.0)
            late_ded_total += float(r.late_deduction or 0.0)
            try:
                mins = int(r.overtime_minutes or 0)
                rate = float(r.overtime_rate or 0.0)
                ot_pay_total += (mins / 60.0) * rate
            except Exception:
                pass

            if str(r.status or "").strip().lower() == "leave":
                if str(r.leave_type or "paid").strip().lower() == "unpaid":
                    unpaid_leave_days += 1
                else:
                    paid_leave_days += 1

    payable_days = max(0, int(attendance.present_days or 0) + int(leave_days := attendance.leave_days or 0))
    # Unpaid leave should not be payable
    payable_days = max(0, payable_days - unpaid_leave_days)

    per_day_rate = base_salary / 30.0 if base_salary > 0 else 0.0
    gross_salary = int(round((per_day_rate * payable_days) + ot_pay_total))

    deductions = Deductions(
        eobi=0,
        tax=0,
        advance=0,
        fine=int(round(fine_total + late_ded_total)),
    )
    net_payable = int(gross_salary - int(deductions.fine or 0))

    return SalaryCalculation(gross_salary=gross_salary, deductions=deductions, net_payable=net_payable)

def _calculate_settlement(inventory_items: List[InventoryItem], salary_calc: SalaryCalculation) -> Settlement:
    """Calculate final settlement amounts"""
    total_to_collect = sum(item.value or 0 for item in inventory_items)
    total_to_pay = max(0, salary_calc.net_payable)
    net_amount = total_to_pay - total_to_collect
    
    return Settlement(
        total_to_collect=total_to_collect,
        total_to_pay=total_to_pay,
        net_amount=net_amount
    )

@router.post("/pending-deactivate", response_model=PendingDeactivationResponse)
async def create_pending_deactivation(
    employee_id: int,
    data: PendingDeactivationCreate,
    db: Session = Depends(get_db)
):
    """Create a pending deactivation request for an employee"""
    global _next_id
    
    # Get employee
    employee = db.query(Employee2).filter(Employee2.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if already pending
    existing = next((p for p in _pending_deactivations if p["employee_db_id"] == employee_id), None)
    if existing:
        raise HTTPException(status_code=400, detail="Employee already has a pending deactivation")
    
    # Calculate all required data
    inventory_items = _get_employee_inventory(db, employee)
    attendance_summary = _calculate_attendance_summary(db, employee, data.deactivation_date)
    salary_calculation = _calculate_salary(db, employee, attendance_summary)
    settlement = _calculate_settlement(inventory_items, salary_calculation)
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
        "id": _next_id,
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
        "avatar_url": employee.avatar_url,
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
    
    _pending_deactivations.append(pending)
    _next_id += 1
    
    return PendingDeactivationResponse(**pending)

@router.get("/pending-deactivate", response_model=List[PendingDeactivationResponse])
async def list_pending_deactivations():
    """List all pending deactivation requests"""
    return [PendingDeactivationResponse(**p) for p in _pending_deactivations]


@router.post("/pending-deactivate/{pending_id}/move-to-inactive")
async def move_to_inactive(pending_id: int, db: Session = Depends(get_db)):
    """Move a pending deactivation to inactive employees"""
    global _pending_deactivations
    
    try:
        # Find pending record
        pending = next((p for p in _pending_deactivations if p["id"] == pending_id), None)
        if not pending:
            raise HTTPException(status_code=404, detail="Pending deactivation not found")
        
        # Get employee
        employee = db.query(Employee2).filter(Employee2.id == pending["employee_db_id"]).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Create inactive employee record with all fields
        inactive_data = {
            "name": pending.get("name") or employee.name or "",
            "fss_no": pending.get("fss_no") or employee.fss_no or "",
            "serial_no": pending.get("serial_no") or employee.serial_no or "",
            "rank": pending.get("rank") or employee.rank or "",
            "cause_of_discharge": employee.discharge_cause or "Discharged",
            "father_name": employee.father_name or "",
            "salary": employee.salary or "0",
            "status": employee.status or "Inactive",
            "cnic": pending.get("cnic") or employee.cnic or "",
            "eobi_no": employee.eobi_no or "",
            "mobile_no": pending.get("mobile_no") or employee.mobile_no or "",
            "district": employee.district or "",
            "doe": employee.enrolled or "",
            "dod": pending.get("deactivation_date") or datetime.now().strftime("%Y-%m-%d"),
            "service_rank": employee.service_rank or "",
            "unit": employee.unit or "",
            "blood_group": employee.blood_group or "",
            "duty_location": employee.duty_location or "",
            "cnic_expiry": employee.cnic_expiry or "",
            "dob": employee.dob or "",
            "domicile": employee.domicile or "",
            "insurance": employee.insurance or "",
            "social_security": employee.social_security or "",
            "vol_no": employee.vol_no or "",
            "home_contact": employee.home_contact or "",
            "verified_by_sho": employee.verified_by_sho or "",
            "verified_by_khidmat_markaz": employee.verified_by_khidmat_markaz or "",
            "verified_by_ssp": employee.verified_by_ssp or "",
            "enrolled": employee.enrolled or "",
            "re_enrolled": employee.re_enrolled or "",
            "village": employee.village or "",
            "post_office": employee.post_office or "",
            "thana": employee.thana or "",
            "tehsil": employee.tehsil or "",
            "police_trg_ltr_date": employee.police_trg_ltr_date or "",
            "vaccination_cert": employee.vaccination_cert or "",
            "payments": employee.payments or "",
            "category": pending.get("category") or employee.category or "",
            "designation": employee.designation or "",
            "allocation_status": "Inactive",
            "bank_accounts": employee.bank_accounts or "[]",
            "avatar_url": employee.avatar_url or "",
            "cnic_attachment": employee.cnic_attachment or "",
            "domicile_attachment": employee.domicile_attachment or "",
            "sho_verified_attachment": employee.sho_verified_attachment or "",
            "ssp_verified_attachment": employee.ssp_verified_attachment or "",
            "khidmat_verified_attachment": employee.khidmat_verified_attachment or "",
            "police_trg_attachment": employee.police_trg_attachment or "",
            "photo_on_doc_attachment": employee.photo_on_doc_attachment or "",
            "served_in_attachment": employee.served_in_attachment or "",
            "vaccination_attachment": employee.vaccination_attachment or "",
            "height": employee.height or "",
            "education": employee.education or "",
            "medical_category": employee.medical_category or "",
            "medical_discharge_cause": employee.medical_discharge_cause or "",
            "nok_name": employee.nok_name or "",
            "nok_relationship": employee.nok_relationship or "",
            "sons_count": employee.sons_count or "0",
            "daughters_count": employee.daughters_count or "0",
            "brothers_count": employee.brothers_count or "0",
            "sisters_count": employee.sisters_count or "0",
            "interviewed_by": employee.interviewed_by or "",
            "introduced_by": employee.introduced_by or "",
            "enrolled_as": employee.enrolled_as or "",
            "served_in": employee.served_in or "",
            "experience_security": employee.experience_security or "",
            "deployment_details": employee.deployment_details or "",
            "discharge_cause": employee.discharge_cause or "",
            "orig_docs_received": employee.orig_docs_received or ""
        }

        # Filter out keys that are not columns on the EmployeeInactive model
        allowed_columns = set(EmployeeInactive.__table__.columns.keys())
        inactive_data = {k: v for k, v in inactive_data.items() if k in allowed_columns}
        
        # Create the inactive employee
        inactive = EmployeeInactive(**inactive_data)
        
        # Add inactive record and delete active record
        try:
            db.add(inactive)
            db.delete(employee)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Database operation failed: {str(e)}"
            )
            
        # Remove from pending deactivations
        _pending_deactivations = [p for p in _pending_deactivations if p["id"] != pending_id]
        
        return {"message": "Employee moved to inactive successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete("/pending-deactivate/{pending_id}")
async def reject_pending_deactivation(pending_id: int):
    """Reject a pending deactivation request."""
    global _pending_deactivations

    pending = next((p for p in _pending_deactivations if p["id"] == pending_id), None)
    if not pending:
        raise HTTPException(status_code=404, detail="Pending deactivation not found")

    _pending_deactivations = [p for p in _pending_deactivations if p["id"] != pending_id]
    return {"message": "Pending deactivation rejected"}
