from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class EmployeeInactive(Base):
    """EmployeeInactive model for discharged/former staff data."""
    
    __tablename__ = "employees_inactive"
    
    id = Column(Integer, primary_key=True, index=True)
    fss_no = Column(String(100), index=True)  # FSS #
    name = Column(Text, nullable=False)  # Name
    father_name = Column(Text)  # Father's Name
    status = Column(Text)  # Status (Army/Civil etc)
    cnic = Column(String(100), index=True)  # CNIC #
    eobi_no = Column(Text)  # EOBI 
    mobile_no = Column(Text)  # Mob #
    district = Column(Text)  # Distt
    doe = Column(Text)  # DOE (Date of Enrollment)
    dod = Column(Text)  # DOD (Date of Discharge)
    cause_of_discharge = Column(Text)  # Cuase of Disch
    police_verification = Column(Text)  # Police Verification
    notice_fine = Column(Text)  # Notice Fine
    uniform_fine = Column(Text)  # Uniform Fine
    police_trg = Column(Text)  # Police Trg
    clo_fine = Column(Text)  # Clo Fine
    vol_no = Column(Text)  # Vol
    
    # Missing fields from Employee2 to ensure full data transfer
    serial_no = Column(String(100), index=True)
    rank = Column(Text)
    salary = Column(Text)
    unit = Column(Text)
    service_rank = Column(Text)
    blood_group = Column(Text)
    status2 = Column(Text)
    unit2 = Column(Text)
    rank2 = Column(Text)
    dob = Column(Text)
    cnic_expiry = Column(Text)
    documents_held = Column(Text)
    documents_handed_over_to = Column(Text)
    photo_on_doc = Column(Text)
    home_contact = Column(Text)
    verified_by_sho = Column(Text)
    verified_by_khidmat_markaz = Column(Text)
    domicile = Column(Text)
    verified_by_ssp = Column(Text)
    enrolled = Column(Text)
    re_enrolled = Column(Text)
    village = Column(Text)
    post_office = Column(Text)
    thana = Column(Text)
    tehsil = Column(Text)
    duty_location = Column(Text)
    police_trg_ltr_date = Column(Text)
    vaccination_cert = Column(Text)
    payments = Column(Text)
    category = Column(Text)
    designation = Column(Text)
    allocation_status = Column(Text)
    bank_accounts = Column(Text)
    
    # Attachments
    avatar_url = Column(Text)
    cnic_attachment = Column(Text)
    domicile_attachment = Column(Text)
    sho_verified_attachment = Column(Text)
    ssp_verified_attachment = Column(Text)
    khidmat_verified_attachment = Column(Text)
    police_trg_attachment = Column(Text)
    photo_on_doc_attachment = Column(Text)
    served_in_attachment = Column(Text)
    vaccination_attachment = Column(Text)
    
    # New fields to match Employee2
    height = Column(Text)
    education = Column(Text)
    medical_category = Column(Text)
    medical_discharge_cause = Column(Text)
    nok_name = Column(Text)
    nok_relationship = Column(Text)
    sons_count = Column(Text)
    daughters_count = Column(Text)
    brothers_count = Column(Text)
    sisters_count = Column(Text)
    interviewed_by = Column(Text)
    introduced_by = Column(Text)
    enrolled_as = Column(Text)
    served_in = Column(Text)
    experience_security = Column(Text)
    deployment_details = Column(Text)
    discharge_cause = Column(Text) # Additional cause field
    orig_docs_received = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<EmployeeInactive {self.fss_no} - {self.name}>"
