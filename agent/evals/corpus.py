"""Source text for the golden contracts.

Contract text lives here rather than as committed PDFs so that it is diffable and
reviewable. `generate.py` renders these to PDF; the PDFs are build artifacts.

Each contract targets a specific failure mode of automated review. The answer keys
in `golden/*.yaml` record ground truth; nothing in this module encodes it.
"""

from __future__ import annotations

PAGE_BREAK = "===PAGE==="

FOOTER = "Confidential - synthetic document generated for evaluation"


# --- 1. Plainly worded, everything present -----------------------------------
# Baseline. A competent reviewer should score this perfectly; if the pipeline
# cannot, nothing downstream is meaningful.

NDA_STANDARD = """
MUTUAL NON-DISCLOSURE AGREEMENT

This Agreement is made between Northwind Data Ltd. and Calder Robotics Inc.

1. Definition of Confidential Information

"Confidential Information" means all non-public information disclosed by either
Party to the other, whether disclosed in writing, orally, electronically, or by
inspection of tangible objects, including business plans, customer lists,
financial data, source code, and technical specifications.

2. Obligations of Confidentiality

The Receiving Party shall hold all Confidential Information in strict confidence
and shall not disclose it to any third party without prior written consent of the
Disclosing Party.

3. Exclusions from Confidential Information

Confidential Information shall not include information that is or becomes publicly
available through no breach of this Agreement, was rightfully in the Receiving
Party's possession before disclosure, is independently developed without reference
to the Confidential Information, or is rightfully obtained from a third party
without restriction. Disclosure required by law or court order is permitted
provided the Receiving Party gives prompt written notice.
===PAGE===
4. Term and Survival

This Agreement commences on the Effective Date and continues for three (3) years.
The confidentiality obligations shall survive expiration or termination of this
Agreement for a further period of five (5) years.

5. Return or Destruction of Materials

Upon termination of this Agreement or upon written request of the Disclosing
Party, the Receiving Party shall return or destroy all Confidential Information in
its possession and shall certify such destruction in writing within thirty (30)
days.

6. No License Granted

No license or other right in or to any patent, copyright, trademark, or other
intellectual property of the Disclosing Party is granted by this Agreement,
whether by implication, estoppel, or otherwise. Each Party retains all right,
title, and interest in its own Confidential Information.

7. Governing Law and Jurisdiction

This Agreement shall be governed by the laws of the State of New York. The Parties
submit to the exclusive jurisdiction of the state and federal courts located in
New York County, New York.
===PAGE===
8. Limitation of Liability

In no event shall the aggregate liability of either Party under this Agreement
exceed the total fees paid in the twelve (12) months preceding the claim. Neither
Party shall be liable for indirect or consequential damages.

9. Injunctive Relief

The Parties acknowledge that a breach of this Agreement would cause irreparable
harm for which monetary damages would be an inadequate remedy. The Disclosing
Party shall be entitled to seek injunctive relief without the necessity of posting
a bond.

10. Entire Agreement

This Agreement constitutes the entire agreement between the Parties with respect
to its subject matter.
"""


# --- 2. Everything present, nothing named conventionally ---------------------
# The false-positive trap. Every obligation exists; none of the operative
# sentences share vocabulary with the clause name in the SOP.

NDA_ODDLY_WORDED = """
CONFIDENTIALITY UNDERTAKING

Between Peregrine Capital LLP and Sundial Manufacturing GmbH.

1. Scope of Protected Material

For the purposes of this Undertaking, "Protected Material" comprises any and all
data, documentation, know-how, and commercial particulars communicated by one
Party to the other, in whatever medium, whether reduced to writing or conveyed
orally at any meeting.

2. Undertakings of the Recipient

The Recipient undertakes to treat all Protected Material with the same degree of
care it applies to its own commercially sensitive material and shall make no
onward communication of it to any person outside its organisation absent the prior
written agreement of the Communicating Party.

3. Matters Falling Outside This Undertaking

The undertakings above do not bite on material which has entered the public domain
otherwise than through the Recipient's default, which the Recipient can evidence
it held before receipt, which it arrives at independently without recourse to the
Protected Material, or which it receives lawfully from a person under no
restriction. Where a court or regulator compels production, the Recipient may
comply upon giving the Communicating Party such notice as is practicable.
===PAGE===
4. Duration

This Undertaking takes effect on the date of signature and remains operative for
thirty-six (36) months. The obligations at clause 2 continue to bind the Recipient
for a further sixty (60) months after that date, notwithstanding the earlier
cessation of this Undertaking.

5. Disposal of Material

Where the Communicating Party so requires in writing, or where this Undertaking
ceases to have effect, the Recipient shall promptly deliver up or destroy every
copy of the Protected Material then within its control, and shall confirm in
writing that it has done so.

6. Reservation of Rights

Nothing in this Undertaking operates to confer on the Recipient any interest in
any patent, registered design, copyright, or other proprietary right belonging to
the Communicating Party. All such rights are reserved to the Communicating Party
absolutely.
===PAGE===
7. Applicable Regime

The construction, validity, and performance of this Undertaking are determined in
accordance with the laws of England and Wales, and the Parties irrevocably submit
disputes arising to the courts of England.

8. General Provisions

In no event shall either Party's aggregate obligation arising under or in
connection with this Undertaking exceed the sums paid or payable between the
Parties in the twelve (12) months preceding the event giving rise to such
obligation. Neither Party shall be answerable to the other for indirect or
consequential losses howsoever arising.

The Parties accept that a departure from clause 2 would occasion harm not capable
of adequate compensation in money, and that the Communicating Party may
accordingly apply to the court for restraint of such conduct without being
required to give any cross-undertaking as to security.

This Undertaking supersedes all prior arrangements between the Parties on this
subject matter.
"""


# --- 3. Headings that look right, obligations negated ------------------------
# The false-negative trap. A reviewer matching on headings scores this as clean.
# The cap and the return obligation are both written out of existence.

NDA_SCOPED_OUT = """
MUTUAL NON-DISCLOSURE AGREEMENT

Between Halverson Biotech Inc. and Tessellate Partners LLC.

1. Definition of Confidential Information

"Confidential Information" means any non-public information disclosed by either
Party, in writing or orally, including technical, financial, and commercial
information.

2. Confidentiality Obligations

The Receiving Party shall not disclose Confidential Information to any third party
without the prior written consent of the Disclosing Party.

3. Exclusions

Confidential Information does not include information that is publicly available,
independently developed, or rightfully received from a third party. Disclosure
compelled by law is permitted on prior written notice.

4. Term and Survival

This Agreement continues for two (2) years from the Effective Date. The
obligations in Section 2 survive termination for three (3) years.
===PAGE===
5. Return of Materials

Upon termination, the Receiving Party may retain copies of Confidential
Information for its internal record-keeping purposes and shall have no obligation
to return or destroy any materials, notes, or analyses derived from the
Confidential Information.

6. No License Granted

Nothing in this Agreement grants the Receiving Party any license or right in the
intellectual property of the Disclosing Party.

7. Governing Law

This Agreement is governed by the laws of the State of Delaware, and the Parties
consent to the exclusive jurisdiction of the courts of Delaware.
===PAGE===
8. Limitation of Liability

Nothing in this Agreement shall operate to limit, exclude, or cap either Party's
liability of any kind, whether arising in contract, tort, or otherwise, and each
Party shall remain fully liable for all losses of every description suffered by
the other Party.

9. Injunctive Relief

The Parties agree that breach of Section 2 would cause irreparable harm and that
the Disclosing Party may seek equitable relief in addition to any other remedy
available at law.

10. Miscellaneous

This Agreement may be amended only in writing signed by both Parties.
"""


# --- 4. Short and genuinely incomplete ---------------------------------------
# The recall test. Four obligations are simply not in the document.

NDA_SPARSE = """
ONE-WAY NON-DISCLOSURE AGREEMENT

Granted by Ardent Logistics Co. in favour of Meridian Advisory Group.

1. Confidential Information

"Confidential Information" means information disclosed by the Disclosing Party to
the Receiving Party, whether in written, oral, or electronic form, that is
designated confidential or that a reasonable person would understand to be
confidential.

2. Non-Disclosure

The Receiving Party shall keep the Confidential Information confidential and shall
not disclose it to any third party.

3. Exceptions

The obligations in Section 2 do not apply to information that is publicly known
through no fault of the Receiving Party, was known to the Receiving Party prior to
disclosure, or is independently developed by the Receiving Party. The Receiving
Party may disclose Confidential Information to the extent required by applicable
law or regulation, provided it notifies the Disclosing Party where permitted.

4. Duration

This Agreement remains in force for two (2) years from the Effective Date, and the
obligations of confidentiality survive for a further two (2) years.

5. Governing Law

This Agreement is governed by and construed in accordance with the laws of the
State of California, and the Parties submit to the exclusive jurisdiction of the
courts of San Francisco County.

6. Notices

Notices under this Agreement shall be given in writing to the addresses set out
above.

7. Counterparts

This Agreement may be executed in counterparts, each of which is deemed an
original.
"""


# --- 5. Everything present, buried in a long document ------------------------
# The retrieval test. Obligations are real but live under generic headings, far
# from where a reviewer would look for them.

MSA_BURIED = """
MASTER SERVICES AGREEMENT

Between Cobalt Integration Services Ltd. and Fairhaven Retail Group plc.

1. Engagement

The Supplier shall provide the services described in each Statement of Work
executed under this Agreement.

2. Charges and Invoicing

The Customer shall pay the charges set out in the applicable Statement of Work
within thirty (30) days of receipt of a valid invoice.

3. Personnel

The Supplier shall ensure that personnel assigned to the services possess
appropriate skills and qualifications.

4. Customer Obligations

The Customer shall provide timely access to premises, systems, and personnel as
reasonably required by the Supplier.

5. Change Control

Any variation to a Statement of Work shall be agreed in writing by both Parties.
===PAGE===
6. Protected Information

"Protected Information" means all information of a confidential nature disclosed
by one Party to the other under or in connection with this Agreement, in any form
and whether or not marked as confidential, including orally imparted information.

7. Handling of Protected Information

Each Party shall keep the other's Protected Information confidential and shall not
disclose it to any third party save as permitted under this Agreement.

8. Permitted Handling

Clause 7 does not apply to information that is in the public domain other than by
breach, was lawfully held before disclosure, is developed independently, or is
lawfully obtained from another source without restriction, nor does it prevent
disclosure required by law, regulation, or a competent authority provided that
prompt notice is given.

9. Data Protection

Each Party shall comply with applicable data protection legislation in performing
this Agreement.

10. Service Levels

Service levels, where applicable, are set out in the relevant Statement of Work.
===PAGE===
11. Duration and Termination

This Agreement commences on the Effective Date and continues for five (5) years
unless terminated earlier in accordance with this clause. Either Party may
terminate for material breach on thirty (30) days' written notice. The obligations
in clause 7 shall survive termination of this Agreement for a period of seven (7)
years.

12. Consequences of Termination

On termination or expiry, each Party shall, at the other's written direction,
return or destroy all Protected Information in its possession or control and
provide written confirmation that it has done so, save for one archival copy
required by law.

13. Intellectual Property

Each Party retains all right, title, and interest in its own intellectual
property. Nothing in this Agreement transfers or licenses any patent, copyright,
database right, or trade mark to the other Party except as expressly stated in a
Statement of Work.

14. Insurance

The Supplier shall maintain professional indemnity insurance of not less than five
million pounds.
===PAGE===
15. Governing Law and Forum

This Agreement and any dispute arising out of it are governed by the laws of
England and Wales, and the Parties irrevocably agree that the courts of England
have exclusive jurisdiction.

16. Force Majeure

Neither Party is liable for failure to perform caused by events beyond its
reasonable control.

17. Assignment

Neither Party may assign this Agreement without the prior written consent of the
other.

18. Miscellaneous

Save in respect of fraud or death or personal injury caused by negligence, the
total aggregate liability of each Party arising under or in connection with this
Agreement shall not exceed the charges paid under the relevant Statement of Work
in the twelve (12) months preceding the event giving rise to the claim, and
neither Party shall be liable for loss of profit, loss of business, or any
indirect or consequential loss.

The Parties acknowledge that damages alone would not be an adequate remedy for
breach of clause 7, and that either Party may seek an injunction or other
equitable relief to restrain a threatened breach without proof of special damage.

No failure or delay in exercising a right constitutes a waiver of it.
"""


# --- 6. Topic mentioned everywhere, obligation nowhere -----------------------
# The keyword trap. Headings and recitals discuss return of materials and
# injunctive relief; no clause actually creates either obligation.

NDA_SYNONYM_TRAP = """
NON-DISCLOSURE AGREEMENT

Between Lyra Semiconductor Inc. and Ashford Ventures LP.

RECITALS

WHEREAS the Parties wish to explore a potential commercial relationship and
recognise the sensitivity of the information to be exchanged, including questions
of confidentiality, the return of materials, and the availability of injunctive
relief in the event of misuse;

WHEREAS the Parties intend that this Agreement record their understanding;

NOW THEREFORE the Parties agree as follows.

1. Confidential Information

"Confidential Information" means non-public information disclosed by either Party
to the other, in written, oral, or electronic form, relating to the business,
products, or technology of the Disclosing Party.

2. Confidentiality

The Receiving Party shall maintain the Confidential Information in confidence and
shall not disclose it to any third party without prior written consent.
===PAGE===
3. Exceptions to Confidentiality

The obligations in Section 2 shall not apply to information that is or becomes
public through no fault of the Receiving Party, was lawfully known before
disclosure, or is independently developed. Disclosure compelled by law or court
order is permitted subject to prompt notice to the Disclosing Party.

4. Term

This Agreement is effective from the Effective Date and shall continue for two (2)
years, and the confidentiality obligations shall survive for three (3) years
thereafter.

5. Return of Materials

The Parties acknowledge the importance of sound information hygiene practices and
have discussed the treatment of materials at the conclusion of their discussions.

6. Remedies

The Parties acknowledge that questions of injunctive relief and irreparable harm
were considered during negotiation of this Agreement.
===PAGE===
7. Ownership

All right, title, and interest in the Confidential Information, including any
intellectual property rights, remain with the Disclosing Party. No license is
granted under this Agreement.

8. Governing Law

This Agreement shall be governed by the laws of the State of Texas, and the
Parties submit to the exclusive jurisdiction of the courts of Travis County,
Texas.

9. Severability

If any provision is held unenforceable, the remaining provisions continue in
effect.

10. Entire Agreement

This Agreement is the entire agreement of the Parties regarding its subject
matter.
"""


CONTRACTS: dict[str, str] = {
    "nda_standard": NDA_STANDARD,
    "nda_oddly_worded": NDA_ODDLY_WORDED,
    "nda_scoped_out": NDA_SCOPED_OUT,
    "nda_sparse": NDA_SPARSE,
    "msa_buried": MSA_BURIED,
    "nda_synonym_trap": NDA_SYNONYM_TRAP,
}


def pages_for(name: str) -> list[list[str]]:
    """Split a contract into pages of lines, ready for rendering."""
    raw = CONTRACTS[name]
    return [page.strip("\n").splitlines() for page in raw.strip().split(PAGE_BREAK)]
