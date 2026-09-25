"""Small, generic gazetteers + vocabularies used by the heuristic recognizers.

These are deliberately generic (common Indian given names/surnames, business vocabulary).
Extend them, or plug in a spaCy/Presidio model, for better recall on unseen names.
"""

FIRST_MALE = set("""
aarav abhay abhishek aditya ajay ajit akash akhil alok amar amit amitabh anand anil ankit ankur anup
anurag arjun arun arvind ashish ashok atul ayush balaji bharat chetan deepak dev dhruv dinesh gaurav
ganesh girish gopal govind harish harsh hemant hitesh imran irfan jagdish jatin javed jay kabir karan
kartik kiran kishore krishna kunal kushal lalit mahesh manish manoj mayank meraj mohan mohit mukesh
nadeem narayan naresh naveen nikhil nilesh nitin pankaj parag paresh pawan piyush pradeep prakash
pranav prashant pratik praveen prem rahul raj rajat rajeev rajendra rajesh rajiv rakesh ram ramesh
ravi rishi rohan rohit sachin sagar sahil salman sameer sandeep sanjay sanjeev santosh satish saurabh
shailesh shankar shashi shivam shyam siddharth srinivas sudhir sumit sunil suresh tarun tushar uday
umesh varun venkatesh vijay vikas vikram vinay vinod vipul vishal vivek yash yogesh zaheer faisal arif
asif aamir shahid farhan anirudh sanket omkar tejas neeraj gautam hemraj kailash madhav mangesh
""".split())

FIRST_FEMALE = set("""
aarti aishwarya anita anjali ankita anushka aparna archana asha bhavna deepa deepika divya gauri
geeta girija heena isha jaya jyoti kajal kavita kavya komal lakshmi lata madhuri mamta meena meera
megha monika nandini neha nisha pooja poonam preeti priya priyanka pushpa rachana radha rakhi rani
rashi rekha renu ritu roshni ruchi sakshi sangeeta sarita seema shalini shikha shilpa shreya shweta
simran sneha sonal sonia sudha sunita swati tanvi usha vandana varsha vidya zoya fatima ayesha sana
nazia apeksha manisha smita sujata suman
""".split())

FIRST_NAMES = FIRST_MALE | FIRST_FEMALE

SURNAMES = set("""
agarwal ahmed ali ansari arora bajaj banerjee bansal bhat bhatt bose chatterjee chauhan chavan chopra
das desai deshmukh deshpande dey dua dubey gaikwad gandhi ghosh goel gupta hegde hussain iyer jadhav
jain jha joshi kamath kapoor kashyap khan khanna kulkarni kumar malhotra mehta menon mirza mishra mittal
mukherjee naidu naik nair oberoi pai pandey patel patil pawar pillai qureshi rane rao reddy rizvi salvi
sawant saxena sen sethi shah sharma sheikh shenoy shetty shinde shukla siddiqui singh sinha srivastava
thakur tiwari trivedi varma verma yadav krishnan sheth parikh modi kothari
""".split())

HONORIFICS = ["Mr", "Mrs", "Ms", "Miss", "Dr", "Shri", "Smt", "Sri", "Kumari", "Kum", "Prof",
              "Late", "Master", "Capt", "Col", "Justice", "Adv", "CA", "CS"]

# Capitalised words that are never (part of) a person name in a prospectus / legal document.
NAME_STOP = set("""
limited ltd private pvt llp company companies board issue offer equity shares share capital section act
regulations regulation sebi icdr lodr india indian government registrar bank banks securities exchange
exchanges national stock director directors promoter promoters group chairman chairperson managing whole
time executive independent non chief financial officer officers secretary compliance the our we and of
for in on at to by with from red herring prospectus draft book running lead manager managers price band
bid bidders bidding anchor investor investors retail qualified institutional buyers risk factors page
annexure schedule table note notes statements restated consolidated standalone total income profit loss
tax ministry corporate affairs reserve maharashtra pune mumbai chakan taloja delhi new road street nagar
plot floor building tower sector phase midc industrial area village taluka district state city january
february march april may june july august september october november december designation address
contact person telephone tel email e-mail website fax registered office corporate details name date
birth dob din pan cin aadhaar father mother spouse husband wife son daughter key managerial personnel
senior management auditor auditors statutory legal counsel sponsor syndicate member members refund
escrow account public collection sponsor designated intermediaries depository participant participants
rta cdp brlm brlms selling shareholder shareholders offered subsidiary subsidiaries associate
entity entities kmp smp sr no s.no sl particulars total amount rs inr crore lakh million billion
details qualification qualifications experience age term period appointment reappointment nominee
nomination remuneration committee audit stakeholders relationship csr resolution general meeting
annual extraordinary chapter part article articles memorandum association objects terms conditions
""".split())

# Tokens that are ordinary English words even though they are also given names.
COMMON_WORD_NAMES = set("""
will mark grace hope faith rose bill frank june april august summer dawn guy jack sunny joy may
art bob chase dean earl ivy lily major miles pat penny ray rich rob sky star victor bank
""".split())

# Generic business vocabulary: kept verbatim inside organisation pseudonyms.
GENERIC_ORG_WORDS = set("""
international india indian industries industrial enterprises enterprise holdings holding group
securities capital finance financial services wealth management advisors advisory advisers consultants
consultancy bank banking investment investments global technologies technology tech solutions systems
engineering engineers infrastructure projects trading exports export imports manufacturing electricals
electrical electronics power energy steel metals chemicals pharma pharmaceuticals healthcare foods
products logistics realty developers estates agro textiles motors auto automotive components private
public limited ltd ltd. pvt pvt. llp inc inc. corporation corp corp. company co co. associates partners
and & of the trust trustee trustees ventures markets broking stock brokers brokerage market asset assets
insurance life general housing credit micro small north south east west central new national united
digital media communications network networks labs research data marketing retail consumer home homes
(india) india) services) plc gmbh ag llc incorporated fintech wires cables cable machinery machines
equipment tools polymers plastics packaging paper printing publishing hospitality hotels travels
transport shipping ports airways aviation mining minerals resources oil gas petroleum cement
constructions construction builders
""".split())

# Public institutions / regulators / market infrastructure: not personal data, never redacted.
DEFAULT_ALLOWLIST = [
    "BSE Limited", "National Stock Exchange of India Limited", "National Securities Depository Limited",
    "Central Depository Services (India) Limited", "Securities and Exchange Board of India",
    "Reserve Bank of India", "Registrar of Companies", "Government of India", "Ministry of Corporate Affairs",
    "Income Tax Department", "Unique Identification Authority of India", "Ministry of Finance",
    "Competition Commission of India", "National Company Law Tribunal", "Supreme Court of India",
    "High Court", "Insolvency and Bankruptcy Board of India", "Institute of Chartered Accountants of India",
    "Institute of Company Secretaries of India", "Metropolitan Stock Exchange of India Limited",
    "Clearing Corporation of India Limited", "NSE Clearing Limited", "Indian Clearing Corporation Limited",
]

ALLOWLIST_DOMAINS = [
    "sebi.gov.in", "bseindia.com", "nseindia.com", "rbi.org.in", "mca.gov.in", "gov.in", "nic.in",
    "incometax.gov.in", "uidai.gov.in", "nsdl.co.in", "cdslindia.com", "icai.org", "icsi.edu",
]

PUBLIC_EMAIL_PROVIDERS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com",
    "live.com", "icloud.com", "protonmail.com", "aol.com", "msn.com", "ymail.com",
}

ROLE_MAILBOX_WORDS = set("""
cs connect info investor investors investorgrievance grievance grievances ipo compliance complaints
contact support admin secretarial legal ir office mail hr careers enquiry enquiries helpdesk
customercare care services mb merchant banking corporate ksh.ipo
""".split())

# ---------------------------------------------------------------- pseudonym pools (clearly fictional)
FAKE_MALE = """John Peter Bruce Clark Tony Steve Harry Oliver James Robert Michael David Daniel Thomas
Charles George Edward Henry Samuel Arthur Walter Frank Albert Oscar Victor Leo Max Felix Hugo Ethan
Lucas Mason Logan Ryan Adam Brian Kevin Jason Eric Paul Scott Grant Dean Neil Owen Ian Carl Glen Roy
Colin Derek Gavin Lewis Miles Nolan Reed Troy Vince Wade Zack""".split()

FAKE_FEMALE = """Jane Mary Diana Natasha Wanda Clara Emma Olivia Sophia Grace Lily Chloe Emily Hannah
Laura Julia Alice Rachel Sarah Megan Lucy Amelia Ruby Ella Zoe Nora Violet Hazel Iris Stella Paige
Tessa Vera Wendy Fiona Gwen Holly Ivy Joan Kate Lena Maya Nina Paula Rita Sofia Tina Uma Wilma Yvonne""".split()

FAKE_SURNAMES = """Doe Parker Kent Rogers Banner Romanoff Maximoff Smith Johnson Williams Brown Jones
Miller Davis Wilson Anderson Taylor Moore Martin Jackson White Harris Lewis Walker Hall Allen Young
King Wright Green Baker Adams Nelson Hill Campbell Mitchell Roberts Carter Phillips Evans Turner Collins
Stewart Morris Murphy Cook Bell Cooper Ward Brooks Gray Watson Hughes Price Bennett Wood Barnes Ross
Foster Powell Russell Sullivan Fisher Hayes Myers Ford Hamilton Graham Wallace Cole Jordan Reynolds
Ellis Stone Hunt Black Palmer Lane Kennedy Warren Dixon Burns Gordon Shaw Holmes Rice Hunter Knight
Hudson Spencer Gardner Payne Pierce Berry Matthews Arnold Wagner Willis Watkins Olson Carroll Duncan
Snyder Hart Cunningham Bradley""".split()

SURNAME_PREFIX = "Ash Black Brook Clay Crest Dal East Fair Glen Hart Hol Kings Lang Mar North Oak Pem Red Rock Stan Thorn Wel West Whit Wind".split()
SURNAME_SUFFIX = "ford wood field ton ley by worth well more dale hurst wick stone bridge man".split()
GIVEN_PREFIX = "Al Bren Cal Dar El Fen Gar Jor Kel Lor Mar Nor Ron Syl Tor Val".split()
GIVEN_SUFFIX = "an en ric ton den vin ius o ley ard".split()

FAKE_BRANDS = """Acme Globex Initech Umbrella Hooli Vandelay Contoso Fabrikam Northwind Tailspin Wonka
Cyberdyne Tyrell Oscorp Aperture Soylent Gringotts Monarch Virtucon Nakatomi Weyland Duff Bluth
Kramerica Sterling Prestige Vortex Nimbus Zenith Orion Helix Lumina Veridian Altura Brightwell
Crestview Evergreen Falcon Granite Harbor Ironclad Juniper Keystone Larkspur Meridian Northstar
Oakridge Pinnacle Quarry Redwood Silverline Trident Summit Willow Zephyr Cobalt Emberly Foxglove
Halcyon Indigo Jasper Kestrel Lodestar Marlin""".split()

ADDR_UNIT = ["Plot No. {n}", "Unit No. {n}", "Gat No. {n}/{m}", "{n}/{m}", "Flat No. {n}", "Survey No. {n}", "Shop No. {n}"]
ADDR_BUILDING = ["Sunrise Towers", "Lakeview Plaza", "Maple Court", "Harbour Heights", "Silver Oak Residency",
                 "Orchid Business Park", "Emerald House", "Crescent Arcade", "Bluebell Chambers", "Cedar Point"]
ADDR_STREET = ["Maple Road", "Oakwood Lane", "Riverside Drive", "Station Road", "Hillcrest Avenue", "Park Street",
               "Lakeshore Marg", "Garden Lane", "Willow Street", "Canal Road"]
ADDR_AREA = ["Greenfield Industrial Estate", "Sunnyvale Nagar", "Lakeview Colony", "Riverbend Phase II",
             "Meadow Park", "Westgate Sector 7", "Pinewood Enclave", "Fairfield Layout"]
ADDR_CITY = ["Springfield", "Rivertown", "Fairview", "Brookside", "Westbury", "Oakdale", "Millbrook",
             "Ashford", "Kingsbridge", "Lakeside", "Riverdale", "Elmwood"]
