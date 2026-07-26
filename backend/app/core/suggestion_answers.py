"""Hand-written answers for the curated questions in `app/core/suggestions.py`.

Seeded directly into the response cache by `scripts/seed_suggestion_cache.py` so
the UI's quick-suggestion chips and `/` picker answer instantly, without waiting
on CPU generation.
"""

SUGGESTED_ANSWERS: dict[str, str] = {
    "What should I check weekly for the chiller plant?": """## Weekly Chiller Plant Checklist

- **Condenser and evaporator pressures** -- compare against design setpoints and log any drift.
- **Refrigerant charge** -- check sight glass or sensor readings for low-charge indicators.
- **Compressor oil level** -- verify it sits within the sight-glass operating range.
- **Condenser water treatment** -- confirm chemical dosing pumps are running and chemical drums are topped up.
- **Strainers and filters** -- inspect and clean condenser water strainers.
- **Vibration and noise** -- listen for abnormal bearing noise on compressors, pumps, and fans.
- **Leak check** -- visually inspect pipework, valves, and fittings for refrigerant or water leaks.
- **BMS alarm review** -- check trend logs for any alarms or trips since the last inspection.

Record all readings on the weekly chiller log sheet, and escalate any out-of-range value to the HVAC contractor the same day.""",
    "Summarize this month's compliance checklist.": """## Monthly Compliance Checklist -- Summary

**Statutory certificates**
- Fire safety NOC, lift licenses, and electrical safety certificates -- confirm none expire within 60 days.

**Inspections completed**
- Fire extinguishers, hose reels, and smoke detectors tested per schedule.
- Emergency lighting and exit signage checked for function.

**Permits and training**
- Hot work and confined-space permits logged and closed out.
- Refresher training (fire warden, first aid) up to date for assigned staff.

**Outstanding items**
- List any overdue inspections or expiring certificates, with the responsible vendor and target close date.

Flag anything expiring within 30 days to the compliance officer immediately, and attach supporting certificates to the monthly compliance file.""",
    "Compare vendor terms for the HVAC contract.": """## Comprehensive vs. Non-Comprehensive HVAC AMC

| Term | Comprehensive AMC | Non-Comprehensive AMC |
| --- | --- | --- |
| Spare parts | Included in contract value | Billed separately, at cost or markup |
| Labor | Included for all PM and breakdown visits | Included for PM only; breakdown labor billed |
| Response time (breakdown) | Typically 2-4 hours | Typically 4-8 hours |
| Preventive visits | Monthly or bi-monthly, per SOP | Quarterly, basic checks only |
| Compressor/major component replacement | Covered | Excluded -- quoted separately |
| Annual cost | Higher fixed cost, predictable budget | Lower fixed cost, variable breakdown spend |

For critical spaces (server rooms, operating areas), a **Comprehensive AMC** is usually the better fit despite the higher cost, since it caps your exposure to large unplanned repair bills and guarantees faster response.""",
    "Draft a memo on an upcoming AMC renewal.": """## MEMORANDUM

**To:** Facilities Management Team
**From:** Facilities Operations
**Subject:** Upcoming AMC Renewal -- Action Required

This is a reminder that one or more Annual Maintenance Contracts (AMCs) are approaching their renewal date. Please review the following before the current term expires:

1. **Performance review** -- confirm the vendor met agreed SLAs (response times, PM completion rate) over the past term.
2. **Pricing** -- request an updated quote and compare against the current rate and at least one alternative vendor.
3. **Scope changes** -- note any new equipment, sites, or services that should be added to the renewed scope.
4. **Approval** -- route the renewal recommendation for sign-off at least 2 weeks before the contract lapses to avoid a coverage gap.

Please confirm receipt and provide your review by the date noted above.

Facilities Management Team""",
    "What's a typical fire safety NOC drill checklist?": """## Fire Safety NOC Drill Checklist

- **Pre-drill notification** -- inform building occupants, security, and the fire department liaison (if required) in advance.
- **Alarm activation** -- trigger the fire alarm system from a designated panel/zone and confirm audibility throughout the building.
- **Evacuation routes** -- verify all exit doors, stairwells, and assembly points are clear and accessible.
- **Headcount** -- floor wardens take attendance at the assembly point and report to the drill coordinator.
- **Response time** -- log the time from alarm activation to full evacuation and compare against the target (commonly under 5-8 minutes).
- **Equipment check** -- confirm emergency lighting, PA announcements, and fire pump/jockey pump operation during the drill.
- **Debrief** -- record observations, near-misses, and corrective actions, and file the drill report for the compliance record.

Drills should be conducted at least twice a year, with results logged for the NOC renewal application.""",
    "Explain the standard preventive maintenance schedule for HVAC systems.": """## Standard HVAC Preventive Maintenance Schedule

**Weekly**
- Filter inspection, belt tension check, condensate drain check.

**Monthly**
- Coil cleaning (condenser/evaporator), lubrication of motors and bearings, refrigerant pressure check.

**Quarterly**
- Electrical connection tightness check, control calibration (thermostats, sensors), fan and blower balancing.

**Semi-Annual**
- Full coil chemical cleaning, compressor performance test, ductwork inspection for leaks/insulation damage.

**Annual**
- Complete system performance audit, vibration analysis on rotating equipment, water treatment system overhaul, BMS controls and setpoint review.

Each visit should be logged with readings (pressures, temperatures, amperage draw) so trends can be tracked over time -- a sudden shift often flags a developing fault before it causes a breakdown.""",
    "What documentation is needed for an electrical certificate renewal?": """## Documents Needed for Electrical Certificate Renewal

- **Previous test certificate** -- the expiring certificate, for reference and continuity of records.
- **Single-line diagram (SLD)** -- updated to reflect any panel or load changes since the last inspection.
- **Thermal imaging report** -- recent infrared scan of panels and major connections, if required by the certifying body.
- **Earthing/grounding test results** -- earth resistance readings for the main earth pit(s).
- **Insulation resistance (IR) test logs** -- for distribution boards and major feeders.
- **Load schedule** -- current connected load vs. design capacity, to confirm no overloading.
- **List of defects rectified** -- evidence (photos, work orders) that issues flagged in the previous inspection were closed out.
- **Authorized signatory details** -- license/registration of the testing engineer or agency.

Submit the package to the certifying authority at least 30 days before the current certificate expires to avoid a lapse.""",
    "What are typical SLA response times for plumbing emergencies?": """## Typical Plumbing Emergency SLA Response Times

| Priority | Example issue | Response time | Resolution target |
| --- | --- | --- | --- |
| Critical | Major leak, flooding, no water supply to a floor | 30-60 minutes | 4 hours |
| High | Blocked drain affecting a restroom/kitchen | 1-2 hours | 8 hours |
| Medium | Dripping tap, slow drain | Same day | 2 business days |
| Low | Cosmetic fixture issue, minor fitting wear | Next business day | 5 business days |

**Critical** issues should trigger an immediate call (not just a logged ticket) to the on-call plumbing contractor, with isolation of the affected water supply if needed to prevent further damage while the technician is en route.""",
    "Summarize the housekeeping SOP for common areas.": """## Housekeeping SOP -- Common Areas

**Multiple times daily**
- Spot-clean entrance glass and high-touch surfaces (door handles, elevator buttons); restock restroom consumables.

**Daily**
- Vacuum/mop lobbies, corridors, and elevator lobbies; empty waste bins; clean and disinfect restrooms; wipe down handrails.

**Weekly**
- Deep-clean restroom fixtures and floors, dust ledges, vents, and signage, clean elevator interiors including tracks.

**Monthly**
- Carpet/upholstery spot treatment, light fixture and high-level dusting, deep-scrub hard floors.

**Quarterly**
- Window cleaning (interior and accessible exterior), deep carpet shampooing, strip and reseal hard floors as needed.

All cleaning chemicals must be stored and labeled per the site's HSE guidelines, and staff should follow the color-coded cloth/equipment system to prevent cross-contamination between restrooms and food-service areas.""",
    "Outline the steps for onboarding a new facilities vendor.": """## Vendor Onboarding Steps

1. **Pre-qualification** -- collect company registration, insurance certificates (liability, workmen's compensation), and relevant trade licenses.
2. **Compliance documents** -- verify HSE policy, safety training records, and any required certifications (e.g., electrical license, fire safety contractor registration).
3. **Contract execution** -- finalize and sign the AMC/service agreement, including SLAs, pricing, and termination terms.
4. **Site induction** -- conduct a safety induction and site walkthrough for the vendor's assigned technicians.
5. **Access provisioning** -- issue site access cards/permits and register technician details with security.
6. **System setup** -- add the vendor to the CMMS/ticketing system and define escalation contacts.
7. **Kickoff review** -- confirm scope, schedule of PM visits, and reporting format with the vendor's account manager.

Keep all onboarding documents in the vendor file and set a reminder to re-verify insurance and licenses before each renewal.""",
    "Draft an email reminding a vendor about an upcoming contract renewal.": """**Subject: Reminder -- Upcoming Contract Renewal**

Dear [Vendor Contact],

I hope you're doing well. This is a friendly reminder that our current service agreement is approaching its renewal date.

To ensure continuity of service without any gap in coverage, could you please share:

- An updated quotation for the renewal term, reflecting any pricing changes.
- Confirmation of current insurance certificates and trade licenses.
- Any proposed changes to scope, schedule, or service levels.

We'd like to complete the review and sign-off at least two weeks before the current contract expires, so a response by [date] would be appreciated.

Thank you for your continued partnership -- please let us know if you'd like to schedule a call to discuss.

Best regards,
Facilities Management Team""",
    "What PPE is required for electrical maintenance work?": """## PPE for Electrical Maintenance Work

- **Insulated gloves** -- rated for the voltage being worked on, with leather over-gloves for mechanical protection.
- **Arc-rated clothing** -- flame-resistant coveralls or shirt/pants rated for the calculated incident energy.
- **Face and eye protection** -- arc-rated face shield plus safety glasses underneath.
- **Insulated tools** -- screwdrivers, pliers, and testers rated for the working voltage.
- **Voltage-rated footwear** -- electrical hazard (EH) rated, non-conductive soles.
- **Hard hat** -- non-conductive, especially when working near overhead conductors.
- **Hearing protection** -- where switchgear operation poses an arc-blast noise risk.

Before any live work, a **lockout-tagout (LOTO)** procedure should be followed and verified with a voltage tester -- PPE is a last line of defense, not a substitute for de-energizing the circuit wherever possible.""",
    "How are ANPR barriers typically maintained in parking facilities?": """## ANPR Barrier Maintenance -- Parking Facilities

**Daily**
- Visual check for physical damage to the boom arm, housing, and camera lens; confirm the barrier opens/closes on a test vehicle.

**Weekly**
- Clean the ANPR camera lens and check the IR illuminator; verify read accuracy against a sample of plates.

**Monthly**
- Lubricate the boom mechanism and hinges, check loop detector sensitivity, and inspect cable glands for water ingress.

**Quarterly**
- Test battery backup/UPS for the barrier controller, verify integration with the parking management software (entry/exit logging, ticketing), and recalibrate the ANPR software if misreads have increased.

**Annually**
- Full mechanical service of the boom motor and gearbox, firmware update check, and review of the camera's field of view for any obstructions (new signage, foliage, etc.).""",
    "What should be included in a monthly energy audit report?": """## Monthly Energy Audit Report -- Key Sections

- **Consumption summary** -- total electricity, water, and (if applicable) gas/fuel usage for the month, with month-on-month and year-on-year comparison.
- **Load breakdown** -- consumption by major system (HVAC, lighting, lifts, server/IT, common areas).
- **Benchmarking** -- energy use intensity (e.g., kWh/m2) compared against target or industry benchmark.
- **Anomalies** -- any unexpected spikes or drops, with likely cause (equipment fault, occupancy change, weather).
- **Savings initiatives** -- status of ongoing efficiency projects (LED retrofits, BMS schedule optimization, etc.) and their measured impact.
- **Cost impact** -- utility spend for the month against budget, highlighting any tariff changes.
- **Recommendations** -- prioritized action items for the next month (e.g., recalibrate setpoints, repair a faulty meter).

Attach raw meter readings and any sub-metering data as supporting appendices.""",
    "List common causes of CCTV downtime and how to fix them.": """## Common Causes of CCTV Downtime

| Cause | Symptom | Fix |
| --- | --- | --- |
| Power supply failure (camera or NVR) | Camera offline, no feed | Check PoE injector/switch port, replace power adapter |
| Network/cabling fault | Intermittent or no signal | Test cable run, replace damaged connectors, check switch port |
| Storage full or HDD failure | Recording stops, playback gaps | Check NVR storage health, replace failing drive, verify retention settings |
| Firmware/software crash | Camera unresponsive, needs reboot | Schedule firmware update, set up automatic health-check alerts |
| Lens obstruction or weather damage | Blurred/blocked image | Clean lens, check housing seal, reposition if obstructed |
| IP conflict | Camera drops intermittently | Assign static IP, check for duplicate addresses on the network |

A weekly health-check report from the NVR (camera status, storage capacity, recording continuity) catches most of these before they become a compliance gap during an audit.""",
    "What's a typical emergency evacuation drill checklist?": """## Emergency Evacuation Drill Checklist

- **Planning** -- schedule the drill, notify building management/security in advance, and brief floor wardens on their roles.
- **Trigger** -- activate the fire alarm or PA announcement to simulate a real emergency.
- **Evacuation** -- occupants proceed via designated routes to the assembly point; wardens sweep their floors for stragglers.
- **Assembly point roll call** -- each warden confirms headcount against the floor's normal occupancy and reports to the drill coordinator.
- **Special needs** -- confirm any occupants requiring assistance were accounted for and assisted per the evacuation plan.
- **Timing** -- record total evacuation time and time-to-first-responder-on-scene (if simulated).
- **Debrief** -- gather feedback on bottlenecks (blocked exits, confusion at stairwells) and update the evacuation plan accordingly.
- **Documentation** -- file the drill report, including headcount, timing, and corrective actions, for the compliance record.""",
    "Summarize best practices for waste disposal compliance.": """## Waste Disposal Compliance -- Best Practices

- **Segregation at source** -- separate general, recyclable, organic, and hazardous waste into clearly labeled, color-coded bins.
- **Licensed haulers** -- use only waste transporters and disposal facilities holding valid environmental authority licenses.
- **Manifests/records** -- retain waste transfer notes or manifests for every collection, especially for hazardous or e-waste, as proof of legal disposal.
- **Hazardous waste handling** -- store items like batteries, fluorescent tubes, and chemical containers in designated, secured areas pending collection.
- **Quantity tracking** -- log monthly waste volumes by category to support sustainability reporting and identify reduction opportunities.
- **Staff training** -- ensure housekeeping and facilities staff know segregation rules and spill-response procedures.
- **Audits** -- periodically verify the hauler's disposal site and licensing remain valid, and retain certificates of destruction for sensitive materials (e.g., shredded documents, decommissioned hard drives).""",
    "Which network/BMS components need regular license renewals?": """## Network/BMS Components Requiring Regular License Renewal

- **Building Management System (BMS) software** -- supervisor/workstation software licenses and any per-point or per-device licensing tiers.
- **Network management software** -- licenses for switch/firewall management platforms and monitoring tools (e.g., SNMP dashboards).
- **Video management system (VMS)** -- per-camera or per-channel licenses for the CCTV recording platform.
- **Access control software** -- per-door or per-card licenses for the access control management server.
- **Firewall/security appliance subscriptions** -- threat intelligence, antivirus, and content-filtering subscriptions, typically annual.
- **Wireless network controller licenses** -- per-access-point licensing for enterprise Wi-Fi controllers.
- **SSL certificates** -- for any BMS/VMS web portals exposed for remote access, renewed annually.

Maintain a single license register with expiry dates, vendor contacts, and renewal cost, reviewed quarterly so nothing lapses unnoticed.""",
    "Draft a short incident report template for a security breach.": """## Security Incident Report Template

**Incident Reference No.:**
**Date/Time of Incident:**
**Location:**
**Reported By:**

**1. Description of Incident**
Brief factual account of what occurred (unauthorized access, breach point, etc.).

**2. Personnel Involved**
Names/roles of staff, security personnel, and any third parties involved or witnessing.

**3. Immediate Actions Taken**
Steps taken at the time (area secured, access revoked, authorities notified, etc.).

**4. Assets/Areas Affected**
Systems, rooms, or assets accessed or compromised.

**5. Evidence Collected**
CCTV footage references, access logs, photographs.

**6. Root Cause (Preliminary)**
Initial assessment of how the breach occurred.

**7. Corrective Actions / Recommendations**
Proposed fixes (e.g., re-issue access cards, patch a door sensor, retrain staff).

**Reported to:** [Management / Police / Client, as applicable]
**Report prepared by:**
**Date:**""",
    "What's included in a quarterly fire extinguisher inspection?": """## Quarterly Fire Extinguisher Inspection -- Checklist

- **Location and accessibility** -- extinguisher is in its designated location, unobstructed, and signage is visible.
- **Pressure gauge** -- needle in the green/operable range (not overcharged or discharged).
- **Physical condition** -- no visible corrosion, dents, leaks, or damage to the hose/nozzle.
- **Pin and tamper seal** -- safety pin in place and tamper seal intact.
- **Inspection tag** -- last inspection date recorded and the unit is within its service interval.
- **Weight check** (for CO2 types) -- weight within the acceptable range stamped on the cylinder.
- **Mounting** -- bracket secure, extinguisher at the correct mounting height.

Any unit that fails inspection should be tagged out of service and replaced immediately, with the defective unit sent for refill/servicing per the manufacturer's schedule.""",
    "What are the ideal temperature and humidity setpoints for an office building?": """## Comfort Setpoints for an Office Building

| Parameter | Recommended range | Notes |
| --- | --- | --- |
| Temperature (occupied) | 23-26 degC (summer), 21-24 degC (winter) | Aim for ~24 degC as a comfortable, energy-efficient middle ground. |
| Relative humidity | 40-60% RH | Below 30% feels dry; above 65% risks condensation and mould. |
| Setback (unoccupied) | +3-4 degC above cooling setpoint | Relax the setpoint after hours to save energy. |
| Fresh air | Per occupancy / CO2 sensor | Keep CO2 under ~1000 ppm for good indoor air quality. |

Raising the cooling setpoint by even 1 degC typically cuts HVAC energy by 3-5%. Use a small dead-band (e.g. cool at 25, heat at 22) so the plant isn't fighting itself, and let the BMS ramp setpoints gradually to avoid comfort complaints.""",
    "What water treatment parameters should I monitor for cooling towers?": """## Cooling Tower Water Treatment -- Key Parameters

| Parameter | Typical target | Why it matters |
| --- | --- | --- |
| pH | 6.5-8.5 | Low pH corrodes metal; high pH encourages scale. |
| Conductivity / TDS | Per system design; controls blowdown | Rising conductivity means concentrating solids -- triggers bleed. |
| Cycles of concentration | 3-6 | Balances water saving against scaling risk. |
| Total hardness | Site-specific | High hardness drives calcium scale on fills and tubes. |
| Free chlorine / biocide residual | 0.2-0.5 ppm free chlorine | Controls biofilm and general bacteria. |
| Legionella | Undetectable / low CFU | Public-health critical -- test periodically per local code. |

Dose scale, corrosion, and biocide chemicals via automatic controllers where possible, log readings on the water-treatment sheet, and schedule periodic Legionella sampling. Any biocide residual dropping to zero or a Legionella-positive result should trigger immediate corrective dosing and a system review.""",
    "What's the escalation path when a vendor repeatedly misses its SLA?": """## Escalation Path for Repeated SLA Breaches

1. **Log and quantify** -- record each missed SLA (date, ticket, target vs. actual) so the pattern is documented, not anecdotal.
2. **Level 1 -- technician/site supervisor** -- raise the immediate breach with the vendor's on-site team and confirm corrective action for the open ticket.
3. **Level 2 -- account manager** -- issue a formal written notice summarising the repeated breaches and request a root-cause explanation and improvement plan within a set timeframe.
4. **Level 3 -- performance review meeting** -- convene with the vendor's management; review the SLA scorecard, agree on measurable targets, and set a probation/monitoring period.
5. **Contractual remedies** -- apply any penalty/liquidated-damages clause, withhold disputed payment, or invoke the cure period per the contract's default clause.
6. **Termination / re-tender** -- if performance doesn't recover within the cure period, trigger the termination clause and begin sourcing an alternative vendor to avoid a coverage gap.

Keep every step in writing and attach it to the vendor file -- a documented escalation trail is essential if you later need to enforce penalties or terminate for cause.""",
    "How do I calculate the AMC cost per square foot?": """## Calculating AMC Cost per Square Foot

**Formula**

> AMC cost per sq ft = Total annual AMC value / Total serviced area (sq ft)

**Worked example**
- Annual AMC value: INR 12,00,000
- Serviced (built-up) area: 50,000 sq ft
- Cost per sq ft = 12,00,000 / 50,000 = **INR 24 per sq ft per year**

**Tips for a meaningful figure**
- Decide whether to use **built-up** or **carpet** area, and apply it consistently across all vendors so comparisons are fair.
- For a **single-system** AMC (e.g. HVAC only), divide by the area that system actually serves, not the whole building.
- Compare on a **like-for-like scope** -- a comprehensive AMC (parts + labour) will naturally show a higher per-sq-ft cost than a non-comprehensive one.
- Track the figure year-on-year; a sharp rise not explained by scope changes is a prompt to re-tender.""",
    "Draft a work order for AC repair on the third floor.": """## WORK ORDER

**Work Order No.:** ________
**Date raised:** ________
**Priority:** High
**Raised by:** Facilities Helpdesk

**Location:** 3rd Floor (specify zone / room no.)
**Asset / Equipment:** Air-conditioning unit (AHU / FCU / split unit -- specify tag no.)

**1. Problem reported**
Air conditioning on the 3rd floor is not cooling / not operating. (Add specifics: no airflow, warm air, water leak, abnormal noise, tripped unit.)

**2. Requested action**
Inspect and repair the affected AC unit; diagnose root cause (refrigerant, compressor, fan, thermostat, drainage, electrical) and restore normal cooling.

**3. Assigned to**
Vendor / in-house technician: ________  |  Contact: ________

**4. Target response / completion**
Response by: ________  |  Completion by: ________ (per SLA)

**5. Parts / materials (if any)**
________________________________________

**6. Work performed / resolution**
________________________________________

**Technician sign-off:** ________  **Date/Time:** ________
**Verified by (Facilities):** ________""",
    "Draft a tenant notice about scheduled water tank cleaning.": """## NOTICE -- Scheduled Water Tank Cleaning

**Date:** ________
**To:** All Tenants / Occupants
**From:** Facilities Management

Please be informed that the building's water storage tanks will undergo scheduled cleaning and disinfection as part of our routine maintenance and hygiene program.

- **Date of work:** ________
- **Time:** ________ to ________
- **Affected supply:** Domestic water supply to (specify floors/zones) will be temporarily interrupted during this period.

**What to expect**
- Water supply will be shut off for the duration of the cleaning.
- On restoration, you may briefly notice slightly discoloured water -- please run taps for a minute to clear the lines.

**We request that you**
- Store sufficient water in advance for essential use during the shutdown.
- Keep taps closed while the supply is off to avoid air locks.

We apologise for the inconvenience and appreciate your cooperation in keeping the building's water systems clean and safe. For any concerns, please contact the Facilities Helpdesk.

Facilities Management Team""",
    "How often should diesel generator (DG) sets be tested and serviced?": """## DG Set Testing & Service Intervals

**Weekly**
- **No-load / off-load test run** -- start the DG and run for ~15-30 minutes to circulate oil, charge batteries, and confirm it starts on demand. Check for leaks, alarms, and abnormal noise.

**Monthly**
- **On-load test** -- run the DG under load (via load bank or actual transfer) to prevent wet-stacking and confirm it can carry the building load. Check coolant, oil, and battery electrolyte levels.

**Quarterly**
- Inspect fuel quality/filters, tighten electrical connections, test the auto-changeover (AMF) panel, and verify exhaust and silencer condition.

**Semi-annual / Annual**
- Full service: change engine oil and filters, replace air/fuel filters as needed, service the cooling system, test/replace batteries, and calibrate protection relays.

**Ongoing**
- Keep fuel topped up and treated (fuel degrades over time), log every run and its parameters, and periodically **load-bank test** standby sets that rarely see real load to burn off carbon build-up.""",
    "What should a facility shift handover report include?": """## Facility Shift Handover Report -- Contents

- **Shift details** -- date, outgoing/incoming shift, and personnel on duty.
- **Open issues / active tickets** -- ongoing breakdowns or complaints, their status, and what the next shift must follow up on.
- **Critical system status** -- HVAC, DG, fire, lifts, BMS, water, and power: normal or any faults/alarms currently active.
- **Utility readings** -- key meter readings (power, water, fuel level in DG tank) at handover.
- **Incidents** -- any safety, security, or operational incident during the shift and actions taken.
- **Vendor / contractor activity** -- who was on site, what work was done or is pending, and any permits still open.
- **Pending tasks** -- scheduled PM, inspections, or deliveries expected in the next shift.
- **Keys / access / assets** -- handover of keys, radios, or access cards, and any discrepancies.

The outgoing supervisor and incoming supervisor should both **sign off** on the report, so accountability transfers cleanly and nothing critical is dropped between shifts.""",
    "What's the checklist for an annual lift/elevator inspection?": """## Annual Lift / Elevator Inspection Checklist

- **Statutory certificate** -- confirm the lift licence/fitness certificate is valid and schedule renewal via the competent authority.
- **Ropes and traction** -- inspect hoist ropes for wear, corrosion, and correct tension; check the traction sheave and governor rope.
- **Brakes** -- test the machine brake holding capacity and the emergency/safety brake operation.
- **Safety gear and buffers** -- verify overspeed governor trip, car safety gear engagement, and buffer condition.
- **Door systems** -- test door interlocks, sensors/light curtains, and re-levelling; doors must not open outside the landing zone.
- **Emergency features** -- alarm bell, intercom/phone, emergency lighting, and Automatic Rescue Device (ARD) if fitted.
- **Controls and levelling** -- check floor-levelling accuracy, ride quality, and control-panel function.
- **Pit and machine room** -- inspect for water ingress, cleanliness, lubrication, and clearance; verify machine-room ventilation.
- **Load test** -- perform full-load/overload test per code where required.

Any safety-critical failure (brakes, interlocks, safety gear) should take the lift **out of service** until rectified. File the signed inspection report for the compliance record.""",
    "What's the standard procedure for handling a fire alarm false trigger?": """## Handling a Fire Alarm False Trigger

1. **Do not assume it's false** -- treat every activation as real until confirmed otherwise. Dispatch security/floor wardens to the triggered zone immediately.
2. **Identify the zone** -- read the fire alarm panel to locate the exact detector/zone in alarm.
3. **Physically verify** -- confirm there is no smoke, heat, or fire at that location before standing anyone down.
4. **If confirmed false** -- silence the alarm at the panel (authorised personnel only), then investigate the cause: dust, steam, cooking fumes, aerosol, a faulty/dirty detector, or accidental call-point activation.
5. **Reset** -- clear the fault and reset the panel only after the cause is understood and the zone is safe. A call point that was broken must be replaced/re-keyed.
6. **Log it** -- record the activation, zone, cause, and corrective action in the fire log. Recurring false alarms from the same detector warrant cleaning, relocation, or replacement.
7. **Notify** -- inform the fire alarm maintenance vendor if it's a device fault, and advise the monitoring station/fire brigade liaison if the signal was transmitted externally.

Frequent false alarms erode occupant trust in the system -- track them and address root causes so a real alarm is never ignored.""",
    "How can I reduce energy consumption during peak load hours?": """## Reducing Energy Use During Peak Load Hours

**Shift and shed load**
- Pre-cool the building before the peak tariff window, then let temperatures drift up slightly during the peak (thermal coasting).
- Stagger start-up of chillers, pumps, and large motors to avoid coincident demand spikes.
- Defer non-critical loads (water heating, EV charging, certain pumps) to off-peak hours.

**Optimise the big consumers**
- Raise cooling setpoints 1-2 degC during peak; each degree typically saves 3-5% HVAC energy.
- Use chiller sequencing and variable-speed drives so plant runs at its most efficient point, not full blast.
- Dim or zone lighting in low-occupancy areas; use daylight harvesting near windows.

**Manage demand**
- Watch the **maximum demand (MD)** meter -- peak-demand charges often cost more than the energy itself. Set BMS alarms as you approach your MD threshold.
- Use on-site DG or battery/solar (if available) to shave the very top of the peak.

**Track it**
- Trend the load curve to see exactly when peaks occur, then target those intervals. Sub-metering makes it obvious which systems to act on first.""",
    "What should a monthly water consumption report track?": """## Monthly Water Consumption Report -- What to Track

- **Total consumption** -- overall metered usage for the month, with month-on-month and year-on-year comparison.
- **Breakdown by source** -- municipal supply, borewell, and tanker water separately, so you can see dependence on each.
- **Breakdown by use** -- domestic/restrooms, cooling-tower make-up, landscaping/irrigation, and flushing (if sub-metered).
- **Recycled/treated water** -- STP output reused for flushing or landscaping, and the resulting freshwater saved.
- **Per-capita / per-sq-ft intensity** -- litres per occupant per day or per sq ft, benchmarked against target.
- **Anomalies** -- unexpected spikes that may indicate a leak, a running overflow, or a stuck valve, with the likely cause.
- **Tanker water cost** -- number of tankers and spend, highlighting any rise.
- **Recommendations** -- leak repairs, fixture retrofits (aerators, dual-flush), or cooling-tower cycle optimisation for the coming month.

Attach raw meter readings and STP logs as appendices. A sudden unexplained rise in consumption is almost always a leak -- investigate promptly before it inflates both the water bill and any damage.""",
}
