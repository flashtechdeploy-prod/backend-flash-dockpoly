"""Employee2 schemas."""

from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class Employee2Base(BaseModel):
    """Base Employee2 schema."""
    serial_no: Optional[str] = None
    fss_no: Optional[str] = None
    rank: Optional[str] = None
    name: str
    father_name: Optional[str] = None
    salary: Optional[str] = None
    status: Optional[str] = None
    unit: Optional[str] = None
    service_rank: Optional[str] = None
    blood_group: Optional[str] = None
    status2: Optional[str] = None
    unit2: Optional[str] = None
    rank2: Optional[str] = None
    cnic: Optional[str] = None
    dob: Optional[str] = None
    cnic_expiry: Optional[str] = None
    documents_held: Optional[str] = None
    documents_handed_over_to: Optional[str] = None
    photo_on_doc: Optional[str] = None
    eobi_no: Optional[str] = None
    insurance: Optional[str] = None
    social_security: Optional[str] = None
    mobile_no: Optional[str] = None
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
    district: Optional[str] = None
    duty_location: Optional[str] = None
    address_details: Optional[str] = None
    temp_village: Optional[str] = None
    temp_post_office: Optional[str] = None
    temp_thana: Optional[str] = None
    temp_tehsil: Optional[str] = None
    temp_district: Optional[str] = None
    temp_city: Optional[str] = None
    temp_phone: Optional[str] = None
    temp_address_details: Optional[str] = None
    police_trg_ltr_date: Optional[str] = None
    vaccination_cert: Optional[str] = None
    vol_no: Optional[str] = None
    payments: Optional[str] = None
    category: Optional[str] = None
    designation: Optional[str] = None
    allocation_status: Optional[str] = None
    # Avatar and attachments
    avatar_url: Optional[str] = None
    cnic_attachment: Optional[str] = None
    domicile_attachment: Optional[str] = None
    sho_verified_attachment: Optional[str] = None
    ssp_verified_attachment: Optional[str] = None
    khidmat_verified_attachment: Optional[str] = None
    police_trg_attachment: Optional[str] = None
    photo_on_doc_attachment: Optional[str] = None
    personal_signature_attachment: Optional[str] = None
    fingerprint_thumb_attachment: Optional[str] = None
    fingerprint_index_attachment: Optional[str] = None
    fingerprint_middle_attachment: Optional[str] = None
    fingerprint_ring_attachment: Optional[str] = None
    fingerprint_pinky_attachment: Optional[str] = None
    employment_agreement_attachment: Optional[str] = None
    served_in_attachment: Optional[str] = None
    vaccination_attachment: Optional[str] = None
    recording_officer_signature_attachment: Optional[str] = None
    experience_security_attachment: Optional[str] = None
    education_attachment: Optional[str] = None
    nok_cnic_attachment: Optional[str] = None
    other_documents_attachment: Optional[str] = None
    bank_accounts: Optional[str] = None  # JSON string
    
    # New fields
    height: Optional[str] = None
    education: Optional[str] = None
    medical_category: Optional[str] = None
    medical_details: Optional[str] = None
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
    head_office: Optional[str] = None
    dod: Optional[str] = None
    discharge_cause: Optional[str] = None
    orig_docs_received: Optional[str] = None


class Employee2Create(Employee2Base):
    """Schema for creating Employee2."""
    pass


class Employee2Update(BaseModel):
    """Schema for updating Employee2."""
    serial_no: Optional[str] = None
    fss_no: Optional[str] = None
    rank: Optional[str] = None
    name: Optional[str] = None
    father_name: Optional[str] = None
    salary: Optional[str] = None
    status: Optional[str] = None
    unit: Optional[str] = None
    service_rank: Optional[str] = None
    blood_group: Optional[str] = None
    status2: Optional[str] = None
    unit2: Optional[str] = None
    rank2: Optional[str] = None
    cnic: Optional[str] = None
    dob: Optional[str] = None
    cnic_expiry: Optional[str] = None
    documents_held: Optional[str] = None
    documents_handed_over_to: Optional[str] = None
    photo_on_doc: Optional[str] = None
    eobi_no: Optional[str] = None
    insurance: Optional[str] = None
    social_security: Optional[str] = None
    mobile_no: Optional[str] = None
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
    district: Optional[str] = None
    duty_location: Optional[str] = None
    address_details: Optional[str] = None
    temp_village: Optional[str] = None
    temp_post_office: Optional[str] = None
    temp_thana: Optional[str] = None
    temp_tehsil: Optional[str] = None
    temp_district: Optional[str] = None
    temp_city: Optional[str] = None
    temp_phone: Optional[str] = None
    temp_address_details: Optional[str] = None
    police_trg_ltr_date: Optional[str] = None
    vaccination_cert: Optional[str] = None
    vol_no: Optional[str] = None
    payments: Optional[str] = None
    category: Optional[str] = None
    designation: Optional[str] = None
    allocation_status: Optional[str] = None
    # Avatar and attachments
    avatar_url: Optional[str] = None
    cnic_attachment: Optional[str] = None
    domicile_attachment: Optional[str] = None
    sho_verified_attachment: Optional[str] = None
    ssp_verified_attachment: Optional[str] = None
    khidmat_verified_attachment: Optional[str] = None
    police_trg_attachment: Optional[str] = None
    photo_on_doc_attachment: Optional[str] = None
    personal_signature_attachment: Optional[str] = None
    fingerprint_thumb_attachment: Optional[str] = None
    fingerprint_index_attachment: Optional[str] = None
    fingerprint_middle_attachment: Optional[str] = None
    fingerprint_ring_attachment: Optional[str] = None
    fingerprint_pinky_attachment: Optional[str] = None
    employment_agreement_attachment: Optional[str] = None
    served_in_attachment: Optional[str] = None
    vaccination_attachment: Optional[str] = None
    recording_officer_signature_attachment: Optional[str] = None
    experience_security_attachment: Optional[str] = None
    education_attachment: Optional[str] = None
    nok_cnic_attachment: Optional[str] = None
    other_documents_attachment: Optional[str] = None
    bank_accounts: Optional[str] = None  # JSON string
    
    # New fields
    height: Optional[str] = None
    education: Optional[str] = None
    medical_category: Optional[str] = None
    medical_details: Optional[str] = None
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
    head_office: Optional[str] = None
    dod: Optional[str] = None
    discharge_cause: Optional[str] = None
    orig_docs_received: Optional[str] = None


class Employee2(Employee2Base):
    """Schema for Employee2 response."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Employee2List(BaseModel):
    """Schema for Employee2 list response."""
    employees: List[Employee2]
    total: int
