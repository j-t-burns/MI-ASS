# Used libraries
import argparse
import regex as re
from io import StringIO
from pyfasta import Fasta
from operator import itemgetter
from settings import *
from EssentialFunctions import *

# Debugging
DEBUGGING = False
time1 = datetime.now()

# Define argument parser
parser = argparse.ArgumentParser()
parser.add_argument('-mic', '--mic', dest='MIC')
parser.add_argument('-mac', '--mac', dest='MAC')
parser.add_argument('-o', '--o', dest='OUT')
parser.add_argument('-reblast', '--rb', dest='RB', action='store_true')

# Get arguments
if DEBUGGING:
	# Pre-setup arguments for use on my computer/server directory
	#args = parser.parse_args('-mic ../../Assembly_Data/Tetrahymena/ttherm_mic_nuc_Proc.fa -mac ../../Assembly_Data/Tetrahymena/Test_File.fasta -o ../../Output_Tetrohymena'.split())
	args = parser.parse_args('-mic ../../Assembly_Data/Trifallax/oxytri_mic_nuc_Proc.fa -mac ../../Assembly_Data/Trifallax/Test_File.fasta -o ../../Output_Trifallax'.split())
	#args = parser.parse_args('-mic Trifallax/oxytri_mic_nuc_Proc.fa -mac Trifallax/oxytri_mac_nuc_Proc.fa -o Trifallax/Output'.split())
	#args = parser.parse_args('-mic Tetrahymena/ttherm_mic_nuc_Proc.fa -mac Tetrahymena/ttherm_mac_nuc_Proc.fa -o Tetrahymena/Output'.split())
else:
	args = parser.parse_args()

# Store arguments in corresponding variables
regExp_5 = Options['Tel_Reg_Exp_5']
regExp_3 = Options['Tel_Reg_Exp_3']
MICfile = args.MIC
MACfile = args.MAC
Output_dir = args.OUT
ReBlast = args.RB

# Check if files are real files
while not os.path.isfile(MICfile):
	print(MICfile, ' is not a file, please input a valid MIC file:')
	MICfile = input()

while not os.path.isfile(MACfile):
	print(MACfile, ' is not a file, please input a valid MAC file:')
	MACfile = input()
	
# Test whether regular expressions are valid one
re_comp_5 = None
re_comp_3 = None
is_Valid_Re = False
while not is_Valid_Re:
	try:
		re_comp_5 = re.compile(regExp_5, re.IGNORECASE)
		is_Valid_Re = True
	except re.error:
		print('The 5\' regular expression is invalid, please type a valid regular expression:')
		regExp_5 = input()

is_Valid_Re = False
while not is_Valid_Re:
	try:
		re_comp_3 = re.compile(regExp_3, re.IGNORECASE)
		is_Valid_Re = True
	except re.error:
		print('The 3\' regular expression is invalid, please type a valid regular expression:')
		regExp_3 = input()

# Create output directory if needed
LogFile = None
try:
	os.makedirs(Output_dir)
	LogFile = open(Output_dir + '/log.txt', 'w')
	LogFile.write(datetime.now().strftime("%I:%M%p %B %d %Y") + ' - Directory ' + Output_dir + ' created\n')
except OSError as exception:
	if exception.errno == errno.EEXIST:
		LogFile = open(Output_dir + '/log.txt', 'w')
		LogFile.write(datetime.now().strftime("%I:%M%p %B %d %Y") + ' - Directory ' + Output_dir + ' found\n')
	else:
		raise

# Set logComment function file attribute
logComment.logFile = LogFile

# Print parsed arguments
if DEBUGGING:
	print(regExp_5, regExp_3, MICfile, MACfile)

# Check if BLAST is installed
output = None
try:
	output = subprocess.check_output("blastn -version".split(" "))
except:
	print('BLAST is not installed on the computer. Please install BLAST to run the program')
	logComment('BLAST is not installed on the computer, program terminated')
	exit()

logComment("BLAST version: " + output.decode(sys.stdout.encoding).split('\n')[0])

# Create output directories
createOutputDirectories(Output_dir)

# Check if MIC hsp directory exists
createMIC_hsp_files = False
if not os.path.exists(Output_dir + "/hsp_mic"):
	createMIC_hsp_files = True
	safeCreateDirectory(Output_dir + "/hsp_mic")

# Create BLAST database, if it doesn't exist
if not os.path.exists(Output_dir + '/blast/mic.nsq'):
	logComment('Building BLAST database from' + MICfile)
	output = subprocess.check_output(("makeblastdb -in " + str(MICfile) + ' -out ' +  Output_dir + '/blast/mic -dbtype nucl -parse_seqids -hash_index').split(" "))
	logComment(output.decode(sys.stdout.encoding))
else:
	logComment("BLAST database for " + MICfile + " found")

# Import MAC fasta file
logComment('Importing MAC fasta file...')
mac_fasta = None
try:
	mac_fasta = Fasta(MACfile)
except Exception as e:
	print("Error while importing fasta file\n" + str(e))
	logComment("Can't import fasta file\n" + str(e))
	exit()

#if DEBUGGING:
#	print(list(mac_fasta.keys()))

# Record number of imported MAC contigs
macCount = len(mac_fasta.keys())
logComment(str(macCount) + ' sequences imported')

# Rough Blast parameters
dust = "yes" if Options['RoughBlastDust'] else "no"
ungapped = " -ungapped " if Options['RoughBlastUngapped'] else ""
maskLowercase = " -lcase_masking " if Options['BlastMaskLowercase'] else ""
	
logComment("BLAST rough pass parameters:\nblastn -task " + Options['RoughBlastTask'] + " -word_size " + str(Options['RoughBlastWordSize']) + " -max_hsps 0 " +
"-max_target_seqs 10000 -dust " + dust + ungapped + maskLowercase + "-num_threads " + str(Options['ThreadCount']) + 
" -outfmt \"10 qseqid sseqid pident length mismatch qstart qend sstart send evalue bitscore qcovs\"\n")

#Fine Blast parameters
dust = "yes" if Options['FineBlastDust'] else "no"
ungapped = " -ungapped " if Options['FineBlastUngapped'] else ""
	
logComment("BLAST fine pass parameters:\nblastn -task " + Options['FineBlastTask'] + " -word_size " + str(Options['FineBlastWordSize']) + " -max_hsps 0 " + 
"-max_target_seqs 10000 -dust " + dust + ungapped + maskLowercase + 
"-outfmt \"10 qseqid sseqid pident length mismatch qstart qend sstart send evalue bitscore qcovs\"" + " -num_threads " + str(Options['ThreadCount']) + "\n")

# Start BLASTing and annotating
logComment('Annotating ' + str(macCount) + ' MAC contigs...')

for contig in sorted(mac_fasta):
	print("Annotating: ", str(contig))

	# create file for masked telomeres
	maskTel_file = open(Output_dir + '/Masked_Contigs/' + str(contig) + '.fa', 'w')
	maskTel_file.write(">" + str(contig) + "\n")
	
	# Get nucleotide seqeunce
	seq = str(mac_fasta[contig])
	
	# List of telomeric sequences
	tel_seq = list()
	
	# Identify 5' telomere
	left_Tel_5 = identifyTelomere(re_comp_5, seq, tel_seq, 5)
	
	# Identify 3' telomere
	right_Tel_3 = identifyTelomere(re_comp_3, seq, tel_seq, 3)
	
	# Sort telomeric sequence positions and mask telomeres
	tel_seq.sort()
	str_pos = 0
	for coord in tel_seq:
		if str_pos != (coord[0] - 1):
			maskTel_file.write(seq[str_pos:(coord[0]-1)].upper())
		maskTel_file.write(seq[(coord[0]-1):(coord[1]-1)].lower())
		str_pos = coord[1] - 1
	# If there are still some letters left to print, print them
	if str_pos != len(seq):
		maskTel_file.write(seq[str_pos:len(seq)].upper())
								
	# Close masked contig file
	maskTel_file.close()
	
	# Run Rough BLAST pass
	MIC_maps = readBLAST_file(Output_dir + "/hsp_mac/rough/" + str(contig) + ".csv") if not ReBlast and os.path.isfile(Output_dir + "/hsp_mac/rough/" + str(contig) + ".csv") else run_Rough_BLAST(Output_dir, str(contig))
		
	# Get MAC start and MAC end with respect to telomeres
	#print(left_Tel_5, " ", right_Tel_3)
	MAC_start = 1 if not left_Tel_5 else left_Tel_5[1] + 1
	MAC_end = len(mac_fasta[contig]) if not right_Tel_3 else right_Tel_3[0] - 1
	#Debuging message		
	#print(contig, " start: ", MAC_start, " end: ", MAC_end)
	
	# Build list of MDSs if there is a BLAST output
	MDS_List = list()
	if MIC_maps != "":
		# Check if need to update MIC hsp files
		if(createMIC_hsp_files):
			update_MIC_hsp(MIC_maps, Output_dir)
			
		# Sort rough BLAST output
		sortHSP_List(MIC_maps)
		
		# Annotate MDSs with rough BLAST hsps
		getMDS_Annotation(MDS_List, MIC_maps, MAC_start, MAC_end)	
	else:
		MIC_maps = list()
	
	# Check if MAC is fully covered, and run fine pass if it is needed
	if getGapsList(MDS_List, MAC_start, MAC_end):
		# Run fine BLAST pass
		fineBLAST = readBLAST_file(Output_dir + "/hsp_mac/fine/" + str(contig) + ".csv") if not ReBlast and os.path.isfile(Output_dir + "/hsp_mac/fine/" + str(contig) + ".csv") else run_Fine_BLAST(Output_dir, str(contig))
		
		# If there is a BLAST output, process it
		if fineBLAST != "":
			# Check if need to update MIC hsp files
			if(createMIC_hsp_files):
				update_MIC_hsp(fineBLAST, Output_dir)
			
			# Sort fine BLAST output 
			sortHSP_List(fineBLAST)
			
			# Improve current annotation with fine BLAST results
			getMDS_Annotation(MDS_List, fineBLAST, MAC_start, MAC_end)
			
			# Make a map of MIC to its hsps
			MIC_to_HSP = dict()
			for hsp in MIC_maps:
				if hsp[1] in MIC_to_HSP:
					MIC_to_HSP[hsp[1]].append(hsp)
				else:
					MIC_to_HSP[hsp[1]] = [hsp]
			
			# Add fine BLAST hsp into MIC_maps list and MIC_to_HSP dictionary if fine hsp is not a subset of some rough hsp
			for hsp in fineBLAST:
				if hsp[1] not in MIC_to_HSP or not [x for x in MIC_to_HSP[hsp[1]] if int(x[5]) <= int(hsp[5]) and int(x[6]) >= int(hsp[6])]:
					MIC_maps.append(hsp)
	
	# Check for gaps and add them to the MDS List
	addGaps(MDS_List, MAC_start, MAC_end)	
		
	# Debugging: Output results and label MDSs
	if DEBUGGING:
		MDS_file = open(Output_dir + '/Annotated_MDS/' + str(contig) + '.tsv', 'w')
		ind = 1
		MDS_List.sort(key = lambda x: x[0])
	
		for mds in MDS_List[:-1]:
			MDS_file.write(str(ind) + '\t' + str(mds[0]) + '\t' + str(mds[1]) + '\t' + str(mds[2]) + '\n')
			mds.append(ind)
			ind += 1
		MDS_file.write(str(ind) + '\t' + str(MDS_List[-1][0]) + '\t' + str(MDS_List[-1][1]) + '\t' + str(MDS_List[-1][2]))
		MDS_List[-1].append(ind)
		MDS_file.close()
	# Label MDSs
	else:
		ind = 1
		MDS_List.sort(key = lambda x: x[0])
		for mds in MDS_List:
			mds.append(ind)
			ind += 1
				
	# Annotate hsp with current MDS list
	mapHSP_to_MDS(MIC_maps, MDS_List)
	
	# Output MIC annotation
	MIC_maps.sort(key=lambda x: (x[1], int(x[7])) if int(x[7]) < int(x[8]) else (x[1], int(x[8])))
	if DEBUGGING:
		MIC_file = open(Output_dir + '/MIC_Annotation/' + str(contig) + '.tsv', 'w')
		prevMIC = ""
		for hsp in MIC_maps:
			if hsp[1] != prevMIC:
				MIC_file.write(hsp[1] + '\tMDS\tMAC start\tMAC end\tMIC start\tMIC end\n')
				prevMIC = hsp[1]
			MIC_file.write('\t' + str(hsp[-1]) + '\t' + hsp[5] + '\t' + hsp[6] + '\t' + hsp[7] + '\t' + hsp[8] + '\n')
		
		MIC_file.close()

	#!!!! Consider creating MIC_to_HSP list optional if user asks for certain function execution
	# Make a map of MIC to its hsps for functions below
	MIC_to_HSP = dict()
	for hsp in MIC_maps:
		if hsp[1] in MIC_to_HSP:
			MIC_to_HSP[hsp[1]].append(hsp)
		else:
			MIC_to_HSP[hsp[1]] = [hsp]
			
	# Update database input files
	if Options['DatabaseUpdate']:
		updateDatabaseInput(MDS_List, MIC_maps, MIC_to_HSP, left_Tel_5, right_Tel_3, len(mac_fasta[contig]), Output_dir, str(contig))
		
	# Update gff file
	updateGFF(str(contig), MDS_List, Output_dir, 1)
	
	# Identify scrambling on the best fitting MIC contigs
	identify_MIC_patterns(MIC_maps, MDS_List, MIC_to_HSP, Output_dir)
	
	
logComment("MAC annotation is finished! Total time spent: " + str(datetime.today() - time1))

logComment("Starting MIC annotation...")
time2 = datetime.today()

# Open MIC fasta file
mic_fasta = Fasta(MICfile)

# For each file in the hsp_mic directory, annotate corresponding MIC
for mic_file in os.listdir(Output_dir + "/hsp_mic"):
	mic = os.path.splitext(mic_file)[0]
	print("Annotating: " + mic)
	HSP_List = readBLAST_file(Output_dir + "/hsp_mic/" + mic + ".csv")
	if HSP_List == "":
		continue

	# Sort HSP list
	sortHSP_List(HSP_List)
			
	# Get MDS annotation of MIC
	MIC_MDS_List = list()
	getMDS_Annotation(MIC_MDS_List, HSP_List, 1, len(mic_fasta[mic]))
		
	# Check for gaps and add them to the MDS List - this is MIC IESs
	addGaps(MIC_MDS_List, 1, len(mic_fasta[mic]))	
	
	# Remove IESs on the ends
	MIC_MDS_List.sort(key=lambda x: x[0])
	if MIC_MDS_List[0][2] == 1:
		MIC_MDS_List.pop(0)
	if MIC_MDS_List[-1][2] == 1:
		MIC_MDS_List.pop(-1)
	# Output MIC annotation for debugging purpose
	if DEBUGGING:
		micOut = open(Output_dir + "/MDS_IES_MIC/" + mic + ".tsv", "w")
		indexMDS = 1
		indexIES = 1
		for m in MIC_MDS_List:
			if m[2] == 0:
				micOut.write("MDS_" + str(indexMDS) + "\t" + str(m[0]) + "\t" + str(m[1]) + "\t" + str(m[2]) + "\n")
				m.append(indexMDS)
				indexMDS += 1
			else:
				micOut.write("IES_" + str(indexIES) + "\t" + str(m[0]) + "\t" + str(m[1]) + "\t" + str(m[2]) + "\n")
				m.append(indexIES)
				indexIES += 1
		micOut.close()
	else:
		indexMDS = 1
		indexIES = 1
		for m in MIC_MDS_List:
			if m[2] == 0:
				m.append(indexMDS)
				indexMDS += 1
			else:
				m.append(indexIES)
				indexIES += 1
	
	# Update MIC annotation database file
	micOut = open(Output_dir + '/Database_Input/mds.tsv', 'a')
	for mds in MIC_MDS_List:
		#Print mds
		micOut.write("\\N\t\\N\t" + mic + "\t" + str(mds[-1]) + "\t" + str(mds[0]) + "\t" + 
		str(mds[1]) + "\t" + str(mds[1] - mds[0] + 1) + "\t" + str(mds[2]) + "\n")
	micOut.close()
	
	# Update MIC gff file
	updateGFF(str(mic), MIC_MDS_List, Output_dir, 2)
	
logComment("MIC annotation is finished! Total time spent: " + str(datetime.today() - time2))

# Outputs stats
logComment("MIC pattern stats:\n\nComplete MAC contigs: " + str(identify_MIC_patterns.complete) + "\nScrambled MAC contigs: " + 
str(identify_MIC_patterns.scrambled) + "\nComplete and Scrambled: " + str(identify_MIC_patterns.complete_scrambled))

# Close all files
LogFile.close()

#Debugging time spent
print("Total time spent: {}".format(datetime.today() - time1))










