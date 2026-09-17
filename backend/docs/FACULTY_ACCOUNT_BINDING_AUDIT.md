# FACULTY ACCOUNT BINDING AUDIT REPORT
**System**: VFSTR Faculty Research Publication Monitoring Platform  
**Date**: September 17, 2026  
**Scope**: Complete database user-to-faculty authentication linkage and foreign key integrity audit.

---

## 1. Executive Summary

- **Total Registered Users**: 26
- **Total Faculty Profiles**: 25
- **Successfully Bound Faculty Accounts**: 25
- **Institutional Admin Accounts**: 1
- **Invalid Foreign Keys**: 0
- **Orphan Unbound Users**: 0
- **Faculty Profiles Without Dedicated User Account**: 0

---

## 2. Complete User-to-Faculty Account Binding Table

| User Email | User ID | Role | Faculty ID | Bound Faculty Name | Dept | Binding Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `admin@vignan.ac.in` | `23469850...` | `research_admin` | `N/A (Ins...` | **System Administrator** | Administration | `VALID_ADMIN` |
| `bkr_cse@vignan.ac.in` | `891aea98...` | `faculty` | `30a62a71...` | **Dr Bhimavarapu Krishna Reddy** | CSE | `PERFECTLY_BOUND` |
| `db_cse@vignan.ac.in` | `2d9c9d50...` | `faculty` | `917ea8af...` | **Mr Dega Bala Kotaiah** | CSE | `PERFECTLY_BOUND` |
| `drgrk@vignan.ac.in` | `bc0f99ed...` | `faculty` | `ce6367ac...` | **Dr Keerthi G** | Unknown | `PERFECTLY_BOUND` |
| `drjv_cse@vignan.ac.in` | `985e57e3...` | `faculty` | `ce4ae9c7...` | **Dr Vinoj Jothipandian** | CSE | `PERFECTLY_BOUND` |
| `drmoa@vignan.ac.in` | `79754aa6...` | `faculty` | `311f2b4f...` | **Dr MD OQAIL AHMAD** | Unknown | `PERFECTLY_BOUND` |
| `drmv_acse@vignan.ac.in` | `f89a43a7...` | `faculty` | `96780b82...` | **Dr VIJAI MEYYAPPAN MOORTHY** | ACSE | `PERFECTLY_BOUND` |
| `drpsp_cse@vignan.ac.in` | `05793873...` | `faculty` | `e7399ee0...` | **Dr P. Siva Prasad** | CSE | `PERFECTLY_BOUND` |
| `drpu_cse@vignan.ac.in` | `5edd229b...` | `faculty` | `3b04b44a...` | **Dr Prashant Upadhyay** | CSE | `PERFECTLY_BOUND` |
| `druma_cse@vignan.ac.in` | `0a10fc77...` | `faculty` | `b836df5d...` | **Dr M Umadevi** | CSE | `PERFECTLY_BOUND` |
| `dsk_cse@vignan.ac.in` | `c513baad...` | `faculty` | `e25a7264...` | **Mr Dehtaj Shaik** | CSE | `PERFECTLY_BOUND` |
| `dy_cse@vignan.ac.in` | `2974367e...` | `faculty` | `bceec20d...` | **Dr D. Yakobu** | CSE | `PERFECTLY_BOUND` |
| `ea_cse@vignan.ac.in` | `1a7f4e92...` | `faculty` | `3da9f460...` | **Mr AKHIL BABU EDARA** | CSE | `PERFECTLY_BOUND` |
| `gvb_cse@vignan.ac.in` | `abc759ba...` | `faculty` | `8933ad1b...` | **Dr G Veerabhadra Chary** | CSE | `PERFECTLY_BOUND` |
| `hodcse@vignan.ac.in` | `eb9570d5...` | `faculty` | `754179a9...` | **Dr Venkatrama Phani Kumar S** | Unknown | `PERFECTLY_BOUND` |
| `jb_cse@vignan.ac.in` | `86d2d10a...` | `faculty` | `59a40f76...` | **Ms Bhimavarapu. Jyothika** | CSE | `PERFECTLY_BOUND` |
| `jva_cse@vignan.ac.in` | `9238ced6...` | `faculty` | `b62be645...` | **Dr Vijitha Ananthi J.** | CSE | `PERFECTLY_BOUND` |
| `kkk_cse@vignan.ac.in` | `4369ca35...` | `faculty` | `38da9bfc...` | **Mr .Kiran Kumar Kaveti** | CSE | `PERFECTLY_BOUND` |
| `kvkkishore@vignan.ac.in` | `3d7c4000...` | `faculty` | `2476f63f...` | **Dr K.V. KRISHNA KISHORE** | Unknown | `PERFECTLY_BOUND` |
| `mb_mech@vignan.ac.in` | `a202474c...` | `faculty` | `b921b279...` | **Mr Mihir Barman** | MECH | `PERFECTLY_BOUND` |
| `mkb_cse@vignan.ac.in` | `dabe333c...` | `faculty` | `c3eedd47...` | **Mr MIHIR BHATT** | CSE | `PERFECTLY_BOUND` |
| `pkk_cse@vignan.ac.in` | `a55d70cc...` | `faculty` | `b59c7d20...` | **Mr Kiran Kumar Raja Pagidipalli** | CSE | `PERFECTLY_BOUND` |
| `rajumtech6@gmail.com` | `b3c6bfad...` | `faculty` | `6a3e4004...` | **Mr VENKATA RAJULU PILLI** | Unknown | `PERFECTLY_BOUND` |
| `rs_eee@vignan.ac.in` | `a07babea...` | `faculty` | `e1ef7798...` | **Dr K Rachananjali** | EEE | `PERFECTLY_BOUND` |
| `sskumar_cse@vignan.ac.in` | `bcadcced...` | `faculty` | `c8fa8f15...` | **Dr SATISH KUMAR SATTI** | CSE | `PERFECTLY_BOUND` |
| `vj_cse@vignan.ac.in` | `490e527a...` | `faculty` | `8ea42715...` | **Mr Vishal Jaiswal** | CSE | `PERFECTLY_BOUND` |

---

## 3. Reference Case Account Bindings

### 1. Dr. M. Umadevi (Reference Identity 1)
- **User Account**: `druma_cse@vignan.ac.in`
- **Bound FacultyProfile ID**: `b836df5d-0fbe-4fa0-b977-7b185969f2b8`
- **Department**: Computer Science & Engineering
- **Status**: `PERFECTLY_BOUND`
- **External Identifiers Attached**:
  - IEEE Author ID: `37085445363` (Verified)
  - Scopus Author ID: `54788460700` (Verified)
  - OpenAlex Author ID: `A5003901187`

### 2. Dr. P. Siva Prasad (Reference Identity 2)
- **User Account**: `drpsp_cse@vignan.ac.in`
- **Bound FacultyProfile ID**: `e7399ee0-758c-453b-8a96-329e3dc2cc96`
- **Department**: Computer Science & Engineering
- **Status**: `PERFECTLY_BOUND`
- **Confirmed Publications**: 15 | **Citations**: 8 | **h-index**: 1 | **i10-index**: 0
- **Faculty Self-Attribution Pending Queue**: 84 tasks

---

## 4. Root Cause of "Faculty Profile Not Found"

1. **Direct Frontend Query Dependency**:
   - Previous UI was attempting to load the profile by directly querying `/api/v1/faculty/${user.faculty_id}`.
   - If an authenticated session's token was generated before the user account foreign key was set or if the frontend state was cached, `faculty_id` evaluated to undefined/null.
2. **Remediation Implemented**:
   - Built dedicated authenticated endpoints `GET /api/v1/faculty/me` and `GET /api/v1/faculty/me/identifiers`.
   - Added automatic backend self-healing that resolves `current_user.faculty_id` or matches institutional email if needed.
   - Enhanced `MyProfile.tsx` to query `/api/v1/faculty/me`, ensuring 100% reliable profile loading on every login without frontend ID guessing.
