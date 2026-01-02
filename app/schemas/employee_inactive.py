from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class EmployeeInactiveBase(BaseModel):
    fss_no: Optional[str] = None
    name: str
    father_name: Optional[str] = None
    status: Optional[str] = None
    cnic: Optional[str] = None
    eobi_no: Optional[str] = None
    mobile_no: Optional[str] = None
    district: Optional[str] = None
    doe: Optional[str] = None
    dod: Optional[str] = None
    cause_of_discharge: Optional[str] = None
    police_verification: Optional[str] = None
    notice_fine: Optional[str] = None
    uniform_fine: Optional[str] = None
    police_trg: Optional[str] = None
    clo_fine: Optional[str] = None
    vol_no: Optional[str] = None
    
    # Matching Employee2 fields for full transfer
    serial_no: Optional[str] = None
    rank: Optional[str] = None
    salary: Optional[str] = None
    unit: Optional[str] = None
    service_rank: Optional[str] = None
    blood_group: Optional[str] = None
    status2: Optional[str] = None
    unit2: Optional[str] = None
    rank2: Optional[str] = None
    dob: Optional[str] = None
    cnic_expiry: Optional[str] = None
    documents_held: Optional[str] = None
    documents_handed_over_to: Optional[str] = None
    photo_on_doc: Optional[str] = None
    home_contact: Optional[str] = None
    verified_by_sho: Optional[str] = None
    verified_by_khidmat_markaz: Optional[str] = None
    domicile: Optional[str] = None
    verified_by_ssp: Optional[str] = None
    enrolled: Optional[str] = None
    re_enrolled: Optional[str] = None
    village: Optional[str] = None
    post_office: Optional[str] = None
    thana: Optional[str] = None
    tehsil: Optional[str] = None
    duty_location: Optional[str] = None
    police_trg_ltr_date: Optional[str] = None
    vaccination_cert: Optional[str] = None
    payments: Optional[str] = None
    category: Optional[str] = None
    designation: Optional[str] = None
    allocation_status: Optional[str] = None
    bank_accounts: Optional[str] = None
    
    # New fields matching Employee2
    height: Optional[str] = None
    education: Optional[str] = None
    medical_category: Optional[str] = None
    medical_discharge_cause: Optional[str] = None
    nok_name: Optional[str] = None
    nok_relationship: Optional[str] = None
    sons_count: Optional[str] = None
    daughters_count: Optional[str] = None
    brothers_count: Optional[str] = None
    sisters_count: Optional[str] = None
    interviewed_by: Optional[str] = None
    introduced_by: Optional[str] = None
    enrolled_as: Optional[str] = None
    served_in: Optional[str] = None
    experience_security: Optional[str] = None
    deployment_details: Optional[str] = None
    discharge_cause: Optional[str] = None
    orig_docs_received: Optional[str] = None
    
    # Attachments
    avatar_url: Optional[str] = None
    cnic_attachment: Optional[str] = None
    domicile_attachment: Optional[str] = None
    sho_verified_attachment: Optional[str] = None
    ssp_verified_attachment: Optional[str] = None
    khidmat_verified_attachment: Optional[str] = None
    police_trg_attachment: Optional[str] = None
    photo_on_doc_attachment: Optional[str] = None
    served_in_attachment: Optional[str] = None
    vaccination_attachment: Optional[str] = None


class EmployeeInactiveCreate(EmployeeInactiveBase):
    pass


class EmployeeInactiveUpdate(EmployeeInactiveBase):
    name: Optional[str] = None


class EmployeeInactive(EmployeeInactiveBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeInactiveList(BaseModel):
    employees: List[EmployeeInactive]
    total: int
