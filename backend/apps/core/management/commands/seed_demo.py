import io
import json
import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pypdf import PdfWriter

from apps.core.models import (
    Application,
    ApplicationDocument,
    ApplicationStatusHistory,
    AuditLog,
    ClassificationRule,
    DocumentType,
    DocumentTypeTranslation,
    DocumentReview,
    FeeSchedule,
    IssuingAgency,
    IssuingAgencyTranslation,
    License,
    LocalAuthority,
    Property,
    PropertyType,
    PropertyTypeDocumentRequirement,
    PropertyTypeTranslation,
    ThaiDistrict,
    ThaiProvince,
    ThaiSubdistrict,
    User,
)
from apps.core.services import capture_requirements


AUTHORITIES = [
    ("PHUKET_PAO", "องค์การบริหารส่วนจังหวัดภูเก็ต"),
    ("PHUKET_CITY", "เทศบาลนครภูเก็ต"),
    ("KATHU_TOWN", "เทศบาลเมืองกะทู้"),
    ("PATONG_MUNICIPALITY", "เทศบาลเมืองป่าตอง"),
    ("KARON_MUNICIPALITY", "เทศบาลตำบลกะรน"),
    ("RATSADA_MUNICIPALITY", "เทศบาลตำบลรัษฎา"),
    ("RAWAI_MUNICIPALITY", "เทศบาลตำบลราไวย์"),
    ("WICHIT_MUNICIPALITY", "เทศบาลตำบลวิชิต"),
    ("CHALONG_MUNICIPALITY", "เทศบาลตำบลฉลอง"),
    ("CHOENG_THALE_MUNICIPALITY", "เทศบาลตำบลเชิงทะเล"),
    ("THEP_KRASATRI_MUNICIPALITY", "เทศบาลตำบลเทพกระษัตรี"),
    ("SI_SUNTHON_MUNICIPALITY", "เทศบาลตำบลศรีสุนทร"),
    ("PA_KHLOK_MUNICIPALITY", "เทศบาลตำบลป่าคลอก"),
    ("KO_KAEO_SAO", "อบต.เกาะแก้ว"),
    ("THEP_KRASATRI_SAO", "อบต.เทพกระษัตรี"),
    ("CHOENG_THALE_SAO", "อบต.เชิงทะเล"),
    ("MAI_KHAO_SAO", "อบต.ไม้ขาว"),
    ("SA_KHU_SAO", "อบต.สาคู"),
    ("KAMALA_SAO", "อบต.กมลา"),
]


PROPERTY_TYPES = {
    "NON_HOTEL_NOTIFICATION": {
        "th": ("สถานที่พักที่ไม่เป็นโรงแรม", "ยื่นแจ้งสถานที่พักตามรายการเอกสารที่ได้รับ"),
        "en": ("Non-hotel accommodation notification", "Notification pathway based on the supplied checklist"),
        "fee": None,
        "issues_license": False,
    },
    "TYPE_1": {
        "th": ("ที่พักแรมประเภทที่ 1", "ข้อมูลตัวอย่างสำหรับการสาธิต"),
        "en": ("Accommodation Type 1", "Demonstration guidance only"),
        "fee": Decimal("10000.00"),
        "issues_license": True,
    },
    "TYPE_2": {
        "th": ("ที่พักแรมประเภทที่ 2", "ข้อมูลตัวอย่างสำหรับการสาธิต"),
        "en": ("Accommodation Type 2", "Demonstration guidance only"),
        "fee": Decimal("20000.00"),
        "issues_license": True,
    },
}


DOCUMENTS = [
    ("HOTEL_APPLICATION_RR1", "OPERATOR_PREPARED", None, "APPLICANT", False, "แบบ ร.ร.๑", "Hotel application form R.R.1"),
    ("NON_HOTEL_NOTIFICATION_FORM", "OPERATOR_PREPARED", None, "APPLICANT", False, "แบบหนังสือแจ้งสถานที่พักที่ไม่เป็นโรงแรม", "Non-hotel accommodation notification form"),
    ("APPLICANT_HOUSE_REGISTRATION", "OPERATOR_PREPARED", None, "APPLICANT", False, "สำเนาทะเบียนบ้านของผู้ยื่นหรือเจ้าของกิจการ", "Applicant or owner house registration copy"),
    ("APPLICANT_ID_CARD", "OPERATOR_PREPARED", None, "APPLICANT", False, "สำเนาบัตรประชาชนของผู้ยื่นหรือเจ้าของกิจการ", "Applicant or owner identity card copy"),
    ("COMPANY_REGISTRATION", "EXTERNAL_AGENCY", "DEMO_BUSINESS_REGISTRY", "APPLICANT", False, "หนังสือรับรองการจดทะเบียนบริษัท (ภายใน ๓ เดือน)", "Company registration certificate issued within three months"),
    ("COMPANY_MOA_AND_REPRESENTATIVE", "OPERATOR_PREPARED", None, "APPLICANT", False, "หนังสือบริคณห์สนธิและหนังสือแต่งตั้งผู้แทนนิติบุคคล", "Memorandum of association and corporate representative appointment"),
    ("PRIMARY_INCOME_EVIDENCE", "OPERATOR_PREPARED", None, "APPLICANT", False, "หลักฐานรายได้หลักของผู้แจ้งหรือหนังสือรับรองรายได้", "Evidence or certification of the notifier's primary income"),
    ("APPLICANT_PHOTO_6X8", "OPERATOR_PREPARED", None, "APPLICANT", False, "รูปถ่ายขนาด ๖ × ๘ เซนติเมตร", "6 × 8 centimetre applicant photograph"),
    ("BUILDING_PERMIT_O1", "EXTERNAL_AGENCY", "DEMO_BUILDING_OFFICE", "PREMISES", False, "ใบอนุญาตก่อสร้างอาคาร (แบบ อ.๑)", "Building permit form O.1"),
    ("BUILDING_MODIFICATION_OR_USE_CERT", "EXTERNAL_AGENCY", "DEMO_BUILDING_OFFICE", "PREMISES", False, "หนังสือรับรองดัดแปลงอาคาร (อ.๕) หรือใบอนุญาตเปลี่ยนการใช้อาคาร (อ.๔)", "Building modification certificate O.5 or building-use change permit O.4"),
    ("BUILDING_PERMIT_OR_CERTIFICATE", "EXTERNAL_AGENCY", "DEMO_BUILDING_OFFICE", "PREMISES", False, "ใบอนุญาตก่อสร้างอาคารหรือหนังสือรับรองอาคาร", "Building permit or building certificate"),
    ("LAND_RIGHT_OR_CONSENT", "OPERATOR_PREPARED", None, "PREMISES", False, "เอกสารสิทธิที่ดินหรือหนังสือยินยอมให้ใช้สถานที่", "Land-right evidence or consent to use the premises"),
    ("LAND_RIGHT_CONSENT_OR_LEASE", "OPERATOR_PREPARED", None, "PREMISES", False, "เอกสารสิทธิที่ดิน หนังสือยินยอมให้ใช้สถานที่ หรือสัญญาเช่า", "Land-right evidence, consent, or lease agreement"),
    ("LOCATION_MAP", "OPERATOR_PREPARED", None, "PREMISES", False, "แผนที่สังเขปหรือแผนที่สถานที่พัก", "Location map or sketch map"),
    ("ACCOMMODATION_HOUSE_REGISTRATION", "EXTERNAL_AGENCY", "DEMO_DISTRICT_OFFICE", "PREMISES", False, "ทะเบียนบ้านของโรงแรมหรือสถานที่พัก", "Accommodation house registration"),
    ("ROOM_LAYOUT_PLAN", "OPERATOR_PREPARED", None, "PREMISES", True, "แบบแปลนหรือแผนผังห้องพัก (ไม่เกิน ๘ ห้อง และ ๓๐ คน)", "Room layout plan (no more than 8 rooms and 30 guests)"),
    ("PARKING_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายบริเวณที่จอดรถ", "Parking area photographs"),
    ("RECEPTION_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายบริเวณฝ่ายต้อนรับ", "Reception area photographs"),
    ("KITCHEN_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายห้องประกอบอาหาร", "Kitchen photographs"),
    ("ROOM_AND_DOOR_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายห้องพักและด้านหลังประตูห้องพัก", "Guest-room and inside-door photographs"),
    ("BUILDING_EXTERIOR_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายอาคารที่ขออนุญาตหรือแจ้ง", "Accommodation building photographs"),
    ("HOTEL_SIGN_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายป้ายชื่อโรงแรม", "Hotel sign photographs"),
    ("NON_HOTEL_SIGN_PHOTOS", "OPERATOR_PREPARED", None, "FACILITIES", True, "ภาพถ่ายป้ายชื่อสถานที่พักที่ระบุคำว่า “สถานที่พัก”", "Non-hotel accommodation sign photographs"),
    ("FIRE_EQUIPMENT_PHOTOS", "OPERATOR_PREPARED", None, "SAFETY", True, "ภาพถ่ายอุปกรณ์ดับเพลิง", "Fire-fighting equipment photographs"),
    ("GAS_STORAGE_PHOTOS", "OPERATOR_PREPARED", None, "SAFETY", True, "ภาพถ่ายที่เก็บถังแก๊ส", "Gas-cylinder storage photographs"),
    ("FIRE_ESCAPE_PLAN_PHOTOS", "OPERATOR_PREPARED", None, "SAFETY", True, "ภาพถ่ายแผนผังทางหนีไฟ", "Fire-escape plan photographs"),
    ("IMPACT_REPORT", "EXTERNAL_AGENCY", "DEMO_LOCAL_AUTHORITY", "SAFETY", False, "หนังสือรายงานผลกระทบ", "Impact assessment report"),
    ("LIABILITY_INSURANCE", "EXTERNAL_AGENCY", "DEMO_INSURANCE_PROVIDER", "SAFETY", False, "หนังสือประกันภัยรวมทั้งประกันภัยบุคคลภายนอก", "Insurance including third-party liability coverage"),
    ("MANAGER_NOTIFICATION_FORM", "OPERATOR_PREPARED", None, "MANAGER", False, "ใบแจ้งเป็นผู้จัดการ", "Manager notification form"),
    ("MANAGER_ID_CARD", "OPERATOR_PREPARED", None, "MANAGER", False, "สำเนาบัตรประชาชนของผู้จัดการ", "Manager identity card copy"),
    ("MANAGER_HOUSE_REGISTRATION", "OPERATOR_PREPARED", None, "MANAGER", False, "สำเนาทะเบียนบ้านของผู้จัดการ", "Manager house registration copy"),
    ("MANAGER_APPOINTMENT_LETTER", "OPERATOR_PREPARED", None, "MANAGER", False, "หนังสือแต่งตั้งผู้จัดการโรงแรม", "Hotel manager appointment letter"),
    ("MANAGER_MEDICAL_CERTIFICATE", "EXTERNAL_AGENCY", "DEMO_HEALTH_PROVIDER", "MANAGER", False, "ใบรับรองแพทย์ของผู้จัดการ", "Manager medical certificate"),
    ("MANAGER_EDUCATION_CERTIFICATE", "OPERATOR_PREPARED", None, "MANAGER", False, "วุฒิการศึกษาของผู้จัดการ", "Manager education certificate"),
    ("MANAGER_PHOTO_6X8", "OPERATOR_PREPARED", None, "MANAGER", False, "รูปถ่ายผู้จัดการขนาด ๖ × ๘ เซนติเมตร", "6 × 8 centimetre manager photograph"),
]


# Fictional values for demonstrating database-driven external guidance. These
# are deliberately not presented as official service levels or legal advice.
EXTERNAL_DOCUMENT_GUIDANCE = {
    "COMPANY_REGISTRATION": {
        "days": 2,
        "th": (
            "ยื่นคำขอผ่านหน่วยงานทะเบียนธุรกิจตัวอย่าง และตรวจสอบข้อกำหนดจริงกับหน่วยงานก่อนดำเนินการ",
            ["เลขทะเบียนนิติบุคคล", "บัตรประชาชนหรือหนังสือมอบอำนาจของผู้ขอ"],
        ),
        "en": (
            "Request the document from the demo business registry and confirm the actual requirements before proceeding.",
            ["Company registration number", "Requester identity document or authorization letter"],
        ),
    },
    "BUILDING_PERMIT_O1": {
        "days": 15,
        "th": (
            "ติดต่อหน่วยงานอาคารตัวอย่างพร้อมแบบอาคาร และยืนยันขั้นตอนจริงกับหน่วยงานผู้รับผิดชอบ",
            ["เอกสารสิทธิหรือหนังสือยินยอมใช้ที่ดิน", "แบบแปลนอาคารสำหรับประกอบคำขอ"],
        ),
        "en": (
            "Contact the demo building office with the building plans and confirm the actual process with the responsible authority.",
            ["Land-right evidence or consent", "Building plans supporting the request"],
        ),
    },
    "BUILDING_MODIFICATION_OR_USE_CERT": {
        "days": 20,
        "th": (
            "ขอคำแนะนำจากหน่วยงานอาคารตัวอย่างก่อนยื่นเรื่องดัดแปลงหรือเปลี่ยนการใช้อาคาร",
            ["ใบอนุญาตหรือข้อมูลอาคารเดิม", "แบบแปลนส่วนที่ดัดแปลงหรือเปลี่ยนการใช้"],
        ),
        "en": (
            "Ask the demo building office for guidance before requesting a modification or change-of-use document.",
            ["Existing building permit or building record", "Plans for the proposed modification or use change"],
        ),
    },
    "BUILDING_PERMIT_OR_CERTIFICATE": {
        "days": 15,
        "th": (
            "ติดต่อหน่วยงานอาคารตัวอย่างเพื่อระบุเอกสารอาคารที่เหมาะกับสถานที่พักนี้",
            ["ข้อมูลที่ตั้งและเลขที่อาคาร", "เอกสารสิทธิหรือหลักฐานการใช้สถานที่"],
        ),
        "en": (
            "Contact the demo building office to identify the appropriate building record for this accommodation.",
            ["Building address and identification details", "Land-right or premises-use evidence"],
        ),
    },
    "ACCOMMODATION_HOUSE_REGISTRATION": {
        "days": 7,
        "th": (
            "ยื่นคำขอที่สำนักทะเบียนตัวอย่าง และตรวจสอบหลักฐานฉบับจริงที่หน่วยงานกำหนด",
            ["เอกสารระบุตัวเจ้าของหรือผู้รับมอบอำนาจ", "หลักฐานเลขที่บ้านหรือเอกสารสิทธิที่เกี่ยวข้อง"],
        ),
        "en": (
            "Request the record from the demo district registry and confirm which originals the office requires.",
            ["Owner or authorized representative identity document", "House-number or related land-right evidence"],
        ),
    },
    "IMPACT_REPORT": {
        "days": 30,
        "th": (
            "สอบถามหน่วยงานท้องถิ่นตัวอย่างเพื่อกำหนดขอบเขตรายงานก่อนจัดทำและยื่นเอกสาร",
            ["ข้อมูลโครงการและการใช้ประโยชน์อาคาร", "แผนที่ตั้งและแนวทางลดผลกระทบเบื้องต้น"],
        ),
        "en": (
            "Ask the demo local authority to confirm the report scope before preparing and submitting it.",
            ["Project and building-use summary", "Location map and preliminary mitigation information"],
        ),
    },
    "LIABILITY_INSURANCE": {
        "days": 3,
        "th": (
            "แจ้งรายละเอียดสถานที่พักและความคุ้มครองที่ต้องการแก่ผู้ให้บริการประกันภัยตัวอย่าง",
            ["รายละเอียดสถานที่พักและจำนวนห้อง", "ข้อมูลผู้เอาประกันภัยและวงเงินคุ้มครองที่ต้องการ"],
        ),
        "en": (
            "Provide the accommodation and requested coverage details to the demo insurance provider.",
            ["Accommodation details and room count", "Insured-party details and requested coverage amount"],
        ),
    },
    "MANAGER_MEDICAL_CERTIFICATE": {
        "days": 1,
        "th": (
            "นัดหมายกับสถานพยาบาลตัวอย่างและสอบถามรายการตรวจที่หน่วยงานรับคำขอกำหนด",
            ["บัตรประชาชนหรือเอกสารระบุตัวผู้จัดการ", "ข้อมูลวัตถุประสงค์ของใบรับรองแพทย์"],
        ),
        "en": (
            "Book an appointment with the demo healthcare provider and confirm the required examination scope.",
            ["Manager identity document", "Purpose required on the medical certificate"],
        ),
    },
}


HOTEL_REQUIREMENT_CODES = [
    "HOTEL_APPLICATION_RR1", "APPLICANT_HOUSE_REGISTRATION", "APPLICANT_ID_CARD",
    "COMPANY_REGISTRATION", "COMPANY_MOA_AND_REPRESENTATIVE", "BUILDING_PERMIT_O1",
    "BUILDING_MODIFICATION_OR_USE_CERT", "PARKING_PHOTOS", "RECEPTION_PHOTOS", "KITCHEN_PHOTOS",
    "ROOM_AND_DOOR_PHOTOS", "FIRE_EQUIPMENT_PHOTOS", "GAS_STORAGE_PHOTOS",
    "BUILDING_EXTERIOR_PHOTOS", "HOTEL_SIGN_PHOTOS", "FIRE_ESCAPE_PLAN_PHOTOS", "LOCATION_MAP",
    "ACCOMMODATION_HOUSE_REGISTRATION", "IMPACT_REPORT", "LAND_RIGHT_OR_CONSENT",
    "LIABILITY_INSURANCE", "MANAGER_NOTIFICATION_FORM", "MANAGER_ID_CARD",
    "MANAGER_HOUSE_REGISTRATION", "MANAGER_APPOINTMENT_LETTER", "MANAGER_MEDICAL_CERTIFICATE",
    "MANAGER_EDUCATION_CERTIFICATE", "MANAGER_PHOTO_6X8",
]


NON_HOTEL_REQUIREMENT_CODES = [
    "NON_HOTEL_NOTIFICATION_FORM", "APPLICANT_HOUSE_REGISTRATION", "APPLICANT_ID_CARD",
    "LAND_RIGHT_CONSENT_OR_LEASE", "BUILDING_PERMIT_OR_CERTIFICATE", "PARKING_PHOTOS",
    "RECEPTION_PHOTOS", "ROOM_AND_DOOR_PHOTOS", "FIRE_EQUIPMENT_PHOTOS",
    "BUILDING_EXTERIOR_PHOTOS", "NON_HOTEL_SIGN_PHOTOS", "FIRE_ESCAPE_PLAN_PHOTOS",
    "LOCATION_MAP", "ACCOMMODATION_HOUSE_REGISTRATION", "ROOM_LAYOUT_PLAN",
    "PRIMARY_INCOME_EVIDENCE", "APPLICANT_PHOTO_6X8",
]


class Command(BaseCommand):
    help = "Idempotently seed fictional HoTLinE Doc demo data."

    @staticmethod
    def demo_pdf_bytes():
        stream = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.write(stream)
        return stream.getvalue()

    @staticmethod
    def ensure_application_event(application, actor, from_status, to_status, action, reason=""):
        ApplicationStatusHistory.objects.get_or_create(
            application=application,
            from_status=from_status,
            to_status=to_status,
            defaults={"actor": actor, "reason": reason},
        )
        AuditLog.objects.get_or_create(
            action=action,
            object_type="core.Application",
            object_id=str(application.pk),
            from_status=from_status,
            to_status=to_status,
            defaults={"actor": actor, "reason": reason},
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv("DEMO_PASSWORD", "DemoPass123!")
        location_path = Path(__file__).resolve().parents[2] / "data" / "phuket_administrative_areas.json"
        location_data = json.loads(location_path.read_text(encoding="utf-8"))
        records = location_data.get("records", [])
        if location_data.get("province_code") != "83" or len(records) != 17:
            raise CommandError("The pinned Phuket administrative-area snapshot is incomplete.")

        for record in records:
            if not (
                record["district_code"].startswith(record["province_code"])
                and record["subdistrict_code"].startswith(record["district_code"])
                and len(record["postal_code"]) == 5
                and record["postal_code"].isdigit()
            ):
                raise CommandError(f"Invalid administrative-area record: {record['subdistrict_code']}")
            province, _ = ThaiProvince.objects.update_or_create(
                code=record["province_code"],
                defaults={
                    "name_th": record["province_name_th"],
                    "name_en": record["province_name_en"],
                    "is_active": True,
                },
            )
            district, _ = ThaiDistrict.objects.update_or_create(
                code=record["district_code"],
                defaults={
                    "province": province,
                    "name_th": record["district_name_th"],
                    "name_en": record["district_name_en"],
                    "is_active": True,
                },
            )
            ThaiSubdistrict.objects.update_or_create(
                code=record["subdistrict_code"],
                defaults={
                    "district": district,
                    "name_th": record["subdistrict_name_th"],
                    "name_en": record["subdistrict_name_en"],
                    "postal_code": record["postal_code"],
                    "is_active": True,
                },
            )

        for property_record in Property.objects.filter(administrative_subdistrict__isnull=True):
            matches = ThaiSubdistrict.objects.filter(
                Q(name_th__iexact=property_record.subdistrict) | Q(name_en__iexact=property_record.subdistrict),
                district__is_active=True,
                is_active=True,
            ).filter(
                Q(district__name_th__iexact=property_record.district)
                | Q(district__name_en__iexact=property_record.district)
            )
            if matches.count() == 1:
                property_record.administrative_subdistrict = matches.first()
                property_record.save(update_fields=["administrative_subdistrict"])

        authorities = {}
        for index, (code, name) in enumerate(AUTHORITIES, start=1):
            authority, _ = LocalAuthority.objects.update_or_create(
                code=code,
                defaults={
                    "official_name": name,
                    "contact_phone": f"076-000-{index:03d}",
                    "contact_email": f"demo-authority-{index}@example.test",
                    "address": "ที่อยู่ตัวอย่าง จังหวัดภูเก็ต",
                    "is_active": True,
                },
            )
            authorities[code] = authority

        property_types = {}
        for code, values in PROPERTY_TYPES.items():
            property_type, _ = PropertyType.objects.update_or_create(
                code=code,
                defaults={"issues_license": values["issues_license"], "is_active": True},
            )
            property_types[code] = property_type
            for language_code in ("th", "en"):
                name, description = values[language_code]
                PropertyTypeTranslation.objects.update_or_create(
                    property_type=property_type,
                    language_code=language_code,
                    defaults={"name": name, "description": description},
                )
            if values["fee"] is None:
                FeeSchedule.objects.filter(property_type=property_type).delete()
            else:
                fee, _ = FeeSchedule.objects.get_or_create(
                    property_type=property_type,
                    currency="THB",
                    effective_from=date(2026, 1, 1),
                    defaults={"amount": values["fee"], "validity_years": 5, "effective_to": None},
                )
                fee.amount = values["fee"]
                fee.validity_years = 5
                fee.effective_to = None
                fee.full_clean()
                fee.save()

        rules = [
            ("OUT_OF_SCOPE", 10, 50, None, None, None, None, "OUT_OF_SCOPE", None, "classification.out_of_scope"),
            ("NOT_HOTEL", 20, None, 8, None, 30, None, "NOT_HOTEL", property_types["NON_HOTEL_NOTIFICATION"], "classification.not_hotel"),
            ("REQUIRES_LICENSE_REVIEW", 30, None, 8, 31, None, None, "REQUIRES_LICENSE_REVIEW", None, "classification.requires_review"),
            ("TYPE_1", 40, 9, 49, None, None, False, "TYPE_1", property_types["TYPE_1"], "classification.type_1"),
            ("TYPE_2", 50, 9, 49, None, None, True, "TYPE_2", property_types["TYPE_2"], "classification.type_2"),
        ]
        rule_objects = {}
        for code, priority, min_rooms, max_rooms, min_guests, max_guests, restaurant, outcome, result_type, guidance in rules:
            rule, _ = ClassificationRule.objects.update_or_create(
                code=code,
                defaults={
                    "priority": priority,
                    "min_rooms": min_rooms,
                    "max_rooms": max_rooms,
                    "min_guests": min_guests,
                    "max_guests": max_guests,
                    "restaurant_value": restaurant,
                    "outcome_code": outcome,
                    "result_property_type": result_type,
                    "guidance_key": guidance,
                    "is_active": True,
                },
            )
            rule.full_clean()
            rule.save()
            rule_objects[code] = rule

        agency_specs = {
            "DEMO_BUILDING_OFFICE": ("หน่วยงานอาคารตัวอย่าง", "Demo building office", "900"),
            "DEMO_BUSINESS_REGISTRY": ("หน่วยงานทะเบียนธุรกิจตัวอย่าง", "Demo business registry", "901"),
            "DEMO_DISTRICT_OFFICE": ("สำนักทะเบียนตัวอย่าง", "Demo district registry", "902"),
            "DEMO_LOCAL_AUTHORITY": ("หน่วยงานท้องถิ่นตัวอย่าง", "Demo local authority", "903"),
            "DEMO_INSURANCE_PROVIDER": ("ผู้ให้บริการประกันภัยตัวอย่าง", "Demo insurance provider", "904"),
            "DEMO_HEALTH_PROVIDER": ("สถานพยาบาลตัวอย่าง", "Demo healthcare provider", "905"),
        }
        agencies = {}
        for code, (th_name, en_name, phone_suffix) in agency_specs.items():
            agency, _ = IssuingAgency.objects.update_or_create(
                code=code,
                defaults={
                    "contact_phone": f"076-000-{phone_suffix}",
                    "contact_email": f"{code.lower().replace('_', '-')}@example.test",
                    "website_url": f"https://example.test/{code.lower().replace('_', '-')}",
                    "is_active": True,
                },
            )
            agencies[code] = agency
            for language_code, name in (("th", th_name), ("en", en_name)):
                IssuingAgencyTranslation.objects.update_or_create(
                    issuing_agency=agency,
                    language_code=language_code,
                    defaults={
                        "name": name,
                        "address": "ที่อยู่ตัวอย่าง จังหวัดภูเก็ต" if language_code == "th" else "Fictional address, Phuket",
                        "contact_notes": "ข้อมูลติดต่อสำหรับสาธิต" if language_code == "th" else "Demo contact details",
                    },
                )

        document_types = {}
        active_document_codes = {item[0] for item in DOCUMENTS}
        DocumentType.objects.exclude(code__in=active_document_codes).update(is_active=False)
        document_steps = {item[0]: item[3] for item in DOCUMENTS}
        for code, category, agency_code, step_code, allows_multiple, th_name, en_name in DOCUMENTS:
            external_guidance = EXTERNAL_DOCUMENT_GUIDANCE.get(code)
            document_type, _ = DocumentType.objects.update_or_create(
                code=code,
                defaults={
                    "category": category,
                    "issuing_agency": agencies.get(agency_code),
                    "approximate_processing_days": external_guidance["days"] if external_guidance else None,
                    "allows_multiple_files": allows_multiple,
                    "is_active": True,
                },
            )
            document_type.full_clean()
            document_type.save()
            document_types[code] = document_type
            for language_code, name in (("th", th_name), ("en", en_name)):
                guidance_translation = external_guidance.get(language_code) if external_guidance else None
                DocumentTypeTranslation.objects.update_or_create(
                    document_type=document_type,
                    language_code=language_code,
                    defaults={
                        "name": name,
                        "description": (
                            "รายการตามบัญชีเอกสารที่ได้รับสำหรับโครงการ ต้องยืนยันข้อกำหนดกับหน่วยงานก่อนใช้งานจริง"
                            if language_code == "th"
                            else "Item from the supplied project checklist; confirm the official requirement before real use"
                        ),
                        "instructions": guidance_translation[0] if guidance_translation else (
                            ("อัปโหลดภาพที่ชัดเจนได้สูงสุด 10 ไฟล์ หรือรวมเป็น PDF หนึ่งไฟล์" if allows_multiple else "อัปโหลดไฟล์ที่อ่านได้ชัดเจนหนึ่งไฟล์")
                            if language_code == "th"
                            else ("Upload up to 10 clear images, or combine them into one PDF" if allows_multiple else "Upload one clear, readable file")
                        ),
                        "supporting_items": "\n".join(guidance_translation[1]) if guidance_translation else "",
                    },
                )

        requirement_sets = (
            (property_types["NON_HOTEL_NOTIFICATION"], NON_HOTEL_REQUIREMENT_CODES),
            (property_types["TYPE_1"], HOTEL_REQUIREMENT_CODES),
            (property_types["TYPE_2"], HOTEL_REQUIREMENT_CODES),
        )
        for property_type, codes in requirement_sets:
            PropertyTypeDocumentRequirement.objects.filter(property_type=property_type).update(is_active=False)
            for index, code in enumerate(codes, start=1):
                PropertyTypeDocumentRequirement.objects.update_or_create(
                    property_type=property_type,
                    document_type=document_types[code],
                    defaults={
                        "is_required": True,
                        "step_code": document_steps[code],
                        "display_order": index,
                        "is_active": True,
                    },
                )

        users = {}
        user_specs = [
            ("applicant@example.test", "ผู้ประกอบการตัวอย่าง", User.Role.APPLICANT, None, False, False),
            ("officer.patong@example.test", "เจ้าหน้าที่ตัวอย่าง ป่าตอง", User.Role.LOCAL_OFFICER, authorities["PATONG_MUNICIPALITY"], False, False),
            ("central@example.test", "เจ้าหน้าที่ส่วนกลางตัวอย่าง", User.Role.CENTRAL_OFFICER, None, False, False),
            ("admin@example.test", "ผู้ดูแลระบบตัวอย่าง", User.Role.SUPER_ADMIN, None, True, True),
        ]
        for email, display_name, role, authority, is_staff, is_superuser in user_specs:
            user, _ = User.objects.get_or_create(email=email, defaults={"display_name": display_name})
            user.display_name = display_name
            user.role = role
            user.local_authority = authority
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.preferred_language = User.Language.THAI
            user.email_verified_at = user.email_verified_at or timezone.now()
            user.set_password(password)
            user.full_clean(exclude=["password"])
            user.save()
            users[email] = user

        analytics_owner, _ = User.objects.get_or_create(
            email="central.analytics.fixtures@example.test",
            defaults={"display_name": "ข้อมูลภาพรวมจังหวัด (ข้อมูลสมมติ)"},
        )
        analytics_owner.display_name = "ข้อมูลภาพรวมจังหวัด (ข้อมูลสมมติ)"
        analytics_owner.role = User.Role.APPLICANT
        analytics_owner.local_authority = None
        analytics_owner.is_staff = False
        analytics_owner.is_superuser = False
        analytics_owner.is_active = False
        analytics_owner.preferred_language = User.Language.THAI
        analytics_owner.email_verified_at = analytics_owner.email_verified_at or timezone.now()
        analytics_owner.set_unusable_password()
        analytics_owner.full_clean(exclude=["password"])
        analytics_owner.save()

        applicant = users["applicant@example.test"]
        patong = authorities["PATONG_MUNICIPALITY"]
        patong_subdistrict = ThaiSubdistrict.objects.get(code="830202")
        samples = [
            ("ที่พักตัวอย่างฉบับร่าง", "DRAFT", "TYPE_1", 20, 40, False),
            ("ที่พักตัวอย่างรอตรวจ", "SUBMITTED", "TYPE_1", 18, 36, False),
            ("ที่พักตัวอย่างรอแก้ไข", "REVISION_REQUIRED", "TYPE_2", 30, 60, True),
            ("ที่พักตัวอย่างอนุมัติ", "APPROVED", "TYPE_1", 16, 32, False),
        ]
        for index, (name, app_status, type_code, rooms, guests, restaurant) in enumerate(samples, start=1):
            property_record, _ = Property.objects.update_or_create(
                owner=applicant,
                name=name,
                defaults={
                    "local_authority": patong,
                    "administrative_subdistrict": patong_subdistrict,
                    "property_type": property_types[type_code],
                    "address_line": f"{90 + index} ถนนตัวอย่าง",
                    "subdistrict": "ป่าตอง",
                    "district": "กะทู้",
                    "province": "ภูเก็ต",
                    "postal_code": "83150",
                    "rooms": rooms,
                    "max_guests": guests,
                    "has_restaurant": restaurant,
                },
            )
            now = timezone.now()
            application, created = Application.objects.get_or_create(
                property=property_record,
                defaults={
                    "responsible_authority": patong,
                    "classification_rule": rule_objects[type_code],
                    "confirmed_property_type": property_types[type_code],
                    "status": app_status,
                    "reference_number": None if app_status == "DRAFT" else f"HTL-2026-9{index:04d}",
                    "rooms_snapshot": rooms,
                    "max_guests_snapshot": guests,
                    "restaurant_snapshot": restaurant,
                    "classification_outcome_snapshot": type_code,
                    "submitted_at": None if app_status == "DRAFT" else now - timedelta(days=index),
                    "approved_at": now if app_status == "APPROVED" else None,
                },
            )
            if created:
                capture_requirements(application)
            else:
                application.responsible_authority = patong
                application.classification_rule = rule_objects[type_code]
                application.confirmed_property_type = property_types[type_code]
                application.status = app_status
                application.reference_number = None if app_status == "DRAFT" else f"HTL-2026-9{index:04d}"
                application.rooms_snapshot = rooms
                application.max_guests_snapshot = guests
                application.restaurant_snapshot = restaurant
                application.classification_outcome_snapshot = type_code
                application.submitted_at = None if app_status == "DRAFT" else application.submitted_at or now - timedelta(days=index)
                application.approved_at = application.approved_at or now if app_status == "APPROVED" else None
                application.save()
                if app_status == "DRAFT":
                    application.requirements.all().delete()
                    capture_requirements(application)
                elif not application.requirements.exists():
                    capture_requirements(application)

            if app_status != "DRAFT":
                target_requirements = list(application.requirements.filter(is_required=True).select_related("document_type"))
                seeded_documents = []
                for requirement_index, requirement in enumerate(target_requirements):
                    storage_key = f"demo_documents/{application.pk}/{requirement.document_type.code}.pdf"
                    if not default_storage.exists(storage_key):
                        default_storage.save(storage_key, ContentFile(self.demo_pdf_bytes()))
                    target_status = ApplicationDocument.Status.UPLOADED
                    if app_status == "APPROVED":
                        target_status = ApplicationDocument.Status.APPROVED
                    elif app_status == "REVISION_REQUIRED":
                        target_status = (
                            ApplicationDocument.Status.REVISION_REQUIRED
                            if requirement_index == 0
                            else ApplicationDocument.Status.APPROVED
                        )
                    ApplicationDocument.objects.filter(
                        application=application,
                        document_type=requirement.document_type,
                        is_current=True,
                    ).update(is_current=False)
                    document, _ = ApplicationDocument.objects.update_or_create(
                        application=application,
                        document_type=requirement.document_type,
                        version=1,
                        attachment_index=1,
                        defaults={
                            "original_filename": f"demo-{requirement.document_type.code.lower()}.pdf",
                            "storage_key": storage_key,
                            "content_type": "application/pdf",
                            "size_bytes": len(self.demo_pdf_bytes()),
                            "status": target_status,
                            "uploaded_by": applicant,
                            "is_current": True,
                        },
                    )
                    seeded_documents.append(document)
                    AuditLog.objects.get_or_create(
                        action="DOCUMENT_UPLOADED",
                        object_type="core.ApplicationDocument",
                        object_id=str(document.pk),
                        defaults={"actor": applicant},
                    )
                    if target_status in {
                        ApplicationDocument.Status.APPROVED,
                        ApplicationDocument.Status.REVISION_REQUIRED,
                    }:
                        reason = "เอกสารตัวอย่างต้องอัปโหลดใหม่" if target_status == ApplicationDocument.Status.REVISION_REQUIRED else ""
                        review, _ = DocumentReview.objects.get_or_create(
                            application_document=document,
                            outcome=target_status,
                            defaults={"reviewer": users["officer.patong@example.test"], "reason": reason},
                        )
                        AuditLog.objects.get_or_create(
                            action="DOCUMENT_REVIEWED",
                            object_type="core.ApplicationDocument",
                            object_id=str(document.pk),
                            to_status=target_status,
                            defaults={
                                "actor": users["officer.patong@example.test"],
                                "reason": reason,
                            },
                        )

                self.ensure_application_event(
                    application,
                    applicant,
                    Application.Status.DRAFT,
                    Application.Status.READY_TO_SUBMIT,
                    "APPLICATION_READY_TO_SUBMIT",
                )
                self.ensure_application_event(
                    application,
                    applicant,
                    Application.Status.READY_TO_SUBMIT,
                    Application.Status.SUBMITTED,
                    "APPLICATION_SUBMITTED",
                )
                if app_status in {"REVISION_REQUIRED", "APPROVED"}:
                    self.ensure_application_event(
                        application,
                        users["officer.patong@example.test"],
                        Application.Status.SUBMITTED,
                        Application.Status.UNDER_REVIEW,
                        "APPLICATION_REVIEW_STARTED",
                    )
                if app_status == "REVISION_REQUIRED":
                    self.ensure_application_event(
                        application,
                        users["officer.patong@example.test"],
                        Application.Status.UNDER_REVIEW,
                        Application.Status.REVISION_REQUIRED,
                        "APPLICATION_REVISION_REQUESTED",
                        "เอกสารตัวอย่างต้องอัปโหลดใหม่",
                    )
            if app_status == "APPROVED":
                fee = FeeSchedule.objects.get(property_type=property_types[type_code], effective_from=date(2026, 1, 1))
                license_record, _ = License.objects.get_or_create(
                    application=application,
                    defaults={
                        "artifact_kind": License.ArtifactKind.HOTEL_LICENSE,
                        "license_number": f"LIC-2026-9{index:04d}",
                        "property_type": property_types[type_code],
                        "fee_schedule": fee,
                        "fee_amount_snapshot": fee.amount,
                        "fee_currency_snapshot": fee.currency,
                        "validity_years_snapshot": fee.validity_years,
                        "issued_at": now,
                        "expires_at": date(now.year + fee.validity_years, now.month, now.day) - timedelta(days=1),
                    },
                )
                self.ensure_application_event(
                    application,
                    users["officer.patong@example.test"],
                    Application.Status.UNDER_REVIEW,
                    Application.Status.APPROVED,
                    "APPLICATION_APPROVED",
                )
                AuditLog.objects.get_or_create(
                    action="LICENSE_ISSUED",
                    object_type="core.License",
                    object_id=str(license_record.pk),
                    defaults={"actor": users["officer.patong@example.test"]},
                )

        fixture_type_codes = ("TYPE_1", "TYPE_2", "NON_HOTEL_NOTIFICATION")
        for authority_index, (authority_code, authority) in enumerate(authorities.items(), start=1):
            if authority_code == "PATONG_MUNICIPALITY":
                continue
            fixture_count = 1 + ((authority_index - 1) % 3)
            for fixture_index in range(1, fixture_count + 1):
                type_code = fixture_type_codes[(authority_index + fixture_index) % len(fixture_type_codes)]
                rule_code = "NOT_HOTEL" if type_code == "NON_HOTEL_NOTIFICATION" else type_code
                if type_code == "NON_HOTEL_NOTIFICATION":
                    rooms, guests, restaurant = 4 + fixture_index, 12 + fixture_index, False
                elif type_code == "TYPE_2":
                    rooms, guests, restaurant = 24 + fixture_index, 48 + fixture_index, True
                else:
                    rooms, guests, restaurant = 10 + fixture_index, 24 + fixture_index, False
                property_name = f"ข้อมูลภาพรวมสมมติ {authority_code} {fixture_index}"
                property_record, _ = Property.objects.update_or_create(
                    owner=analytics_owner,
                    name=property_name,
                    defaults={
                        "local_authority": authority,
                        "property_type": property_types[type_code],
                        "address_line": f"{100 + authority_index}/{fixture_index} ถนนข้อมูลสมมติ",
                        "subdistrict": authority.official_name,
                        "district": "จังหวัดภูเก็ต",
                        "province": "ภูเก็ต",
                        "postal_code": "83000",
                        "rooms": rooms,
                        "max_guests": guests,
                        "has_restaurant": restaurant,
                    },
                )
                application, _ = Application.objects.get_or_create(
                    property=property_record,
                    defaults={
                        "responsible_authority": authority,
                        "classification_rule": rule_objects[rule_code],
                        "confirmed_property_type": property_types[type_code],
                        "status": Application.Status.DRAFT,
                        "rooms_snapshot": rooms,
                        "max_guests_snapshot": guests,
                        "restaurant_snapshot": restaurant,
                        "classification_outcome_snapshot": rule_code,
                    },
                )
                application.responsible_authority = authority
                application.classification_rule = rule_objects[rule_code]
                application.confirmed_property_type = property_types[type_code]
                application.status = Application.Status.DRAFT
                application.reference_number = None
                application.rooms_snapshot = rooms
                application.max_guests_snapshot = guests
                application.restaurant_snapshot = restaurant
                application.classification_outcome_snapshot = rule_code
                application.submitted_at = None
                application.approved_at = None
                application.save()
                application.requirements.all().delete()
                capture_requirements(application)

        self.stdout.write(self.style.SUCCESS("Demo data is ready (fictional data only)."))
