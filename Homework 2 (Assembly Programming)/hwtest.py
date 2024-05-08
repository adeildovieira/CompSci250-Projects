#!/usr/bin/env python3

import sys,os,re
import json # for reading our config as well as gradescope stuff
import shutil # for copying files
import subprocess # for launching stuff
import xml.etree.ElementTree as ET # for parsing Logisim XML
import argparse # for command line switches
import time # for time elapsed
import glob # for clean support
from collections import OrderedDict # to keep json read in-order
try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest # for python 2.x [PY2]
try:
    from subprocess import DEVNULL
except ImportError: 
    DEVNULL = open("/dev/null","w") # for python 2 [PY2]

###############################################
## ECE/CS 250 test tool v3.0 by Tyler Bletsch
##
## 3.0.0: 2021-07-12. Huge refactor to move to OO approach, add features, clean up and formalize many improvements made over the last few years.
##
## Simultaneously Python 2 and Python 3 compatible (ugh).
## TODO: Once the default Python on Mac+Linux is 3.x, scrub this script of the tons of ugly Python 2 compatability hacks. They're all labeled [PY2]. 
##
###############################################

VERSION = "3.0.0"

DEFAULT_TEST_DIR = "tests"

SETTINGS_FILENAME = 'settings.json' #  to be found in the test_dir

VALID_TEST_MODES = ["exe", "spim", "logisim", "java"]
VALID_DIFF_TYPES = ["normal", "float"]

# the gradescope top-level message starts with this.
GRADESCOPE_MESSAGE_HEADER = \
"""Some test cases are hidden until after the late deadline has passed.
NOTE: late penalties as well as certain penalties regarding disallowed components and
code are not applied by the autograder and will be applied manually before the final
grade is posted.

"""

SETTINGS_DEFAULT = {
    'timeout': 10,
    'spim_command': "spim",
    'logisim_jar': "logisim_ev_cli.jar",
}

OUTPUT_MAX_BYTES = 1024*1024  # truncate diff/actual to at most this many bytes in gradescope output

EXITCODE_VALGRIND_ERROR = 88 # arbitrary, just needs to not match a common exit code
EXITCODE_SEGFAULT = -11      # exitcode received from check_call on segfault
EXITCODE_TIMEOUT = -999      # exitcode to synthesize if a timeout is encountered

verbose = False  # if true, command executions get echoed. set by -v option
has_valgrind = True

# ternary operator
def iff(c,a,b):
    if c: return a
    else: return b

# print only if global verbose mode is turned on
def verbose_print(s):
    global verbose
    if verbose: 
        print(TextColors.BLUE + s + TextColors.END)

# quick lil function to indent a string with embedded newlines. doesn't indent entirely blank lines.
def indent(s,n):
    return re.sub('^(.)',' '*n + r'\1',s,flags=re.M)

class TextColors:
    """
    Terminal colors for use in print.
    """
    GREEN = "\033[0;32;92m"
    RED = "\033[0;31;91m"
    DARKGREY =  "\033[0;90m"
    BLUE = "\033[0;34m"
    END = "\033[0m"
    
class Utility:
    @staticmethod
    def logisim_get_components(filename):
        """
        Returns set of component names used by the given circuit (including custom subcircuits)
        """
        
        tree = ET.parse(filename)
        root = tree.getroot()

        components_found = set()

        for child in root:
            if child.tag == "circuit":
                for subchild in child:
                    if subchild.tag == "comp":
                        components_found.add(subchild.attrib["name"])
        return components_found
        
    @staticmethod
    def logisim_get_components_used_per_circuit(filename):
        """
        Get all components used, breaking the result out per subcircuits. Returns a set of (circuit_name, component_name) tuples.
        """
        tree = ET.parse(filename)
        root = tree.getroot()

        seen = set()

        for child in root:
            if child.tag == "circuit":
                circ_name = child.attrib['name']
                for subchild in child:
                    if subchild.tag == "comp":
                        comp_name = subchild.attrib["name"]
                        seen.add((circ_name,comp_name))
        return seen
        
        
    @staticmethod
    def verify_executable(exe, use_path=False):
        """
        Confirm that the exe given is usable executable. If so, returns the executable (expanded to a full path if use_path is on), else None.
        The use_path option checks for the program in the PATH environment if exe is a bare name, or just checks a relative/absolute path'd exe otherwise
        (this is the behavior of the 'which' command).
        """
        if not use_path: 
            if os.access(exe, os.X_OK):
                return exe
            else:
                return None
        choices = subprocess.Popen(["which","-a",exe],stdout=subprocess.PIPE).stdout.read().decode('utf-8').strip().split("\n")
        if choices:
            return choices[0]
        else:
            return None
        
    found_java=None
    @staticmethod
    def find_java():
        """
        Java virtual machine choice is a carnival of trash -- this function tries to find the best java for our task.
        Includes hard coded paths where Mac likes to hide its Java, otherwise searches the path and checks version output to find the Java most likely to work.
        Memoized (repeated calls will cache result).
        """
        if Utility.found_java is not None:
            return Utility.found_java
        Utility.found_java = Utility.real_find_java()
        return Utility.found_java
        
    @staticmethod
    def real_find_java():
        """
        Actual searcher for java used by find_java().
        """
        
        # collect choices of possible javas
        choices = [
            '/Library/Internet Plug-Ins/JavaAppletPlugin.plugin/Contents/Home/bin/java',
            '/Library/Java/JavaVirtualMachines/1.6.0.jdk/Contents/Home/bin/java',
        ] # mac hides their java in these places, outside of PATH. Thanks, mac.
        choices += subprocess.Popen(["which","-a","java"],stdout=subprocess.PIPE).stdout.read().decode('utf-8').strip().split("\n") # find the PATH based ones
        verbose_print("find_java: Choices: %s"%choices)
        first_found = None  # note the first java we find that exists
        first_found_version = None
        best_found = None   # note the java that matches the known good version number
        best_found_version = None
        for java in choices:
            # either non-existent or non-executable? skip
            if not os.access(java, os.X_OK): 
                verbose_print("find_java: %s: not a valid executable" % java)
                continue
                
            # get the version. the decode() stuff and b"\n" is a tapdance to work on both python2 and python3 [PY2]
            pp = subprocess.Popen([java,"-version"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            version_str = pp.stdout.read().strip() + b"\n" + pp.stderr.read().strip() # eat both stdout and stderr, because who knows which it prints to in each version
            version_str = version_str.decode('utf-8')
            version_match = re.search(r'.* version "([^"]+)"',version_str)
            
            # if we can't even parse a version, that's a bad sign. skip it
            if not version_match:
                verbose_print("find_java: %s: couldn't parse version output" % java)
                continue
            
            version = version_match.group(1)
            verbose_print("find_java: %s: %s" % (java,version))
            
            if not first_found: 
                first_found = java
                first_found_version = version
                
            # i've seen the logisim cli work with java 1.6, 1.7, and 1.8, so we prefer those. 
            if re.match(r'1\.[678]\.',version):
                best_found = java # this matches the versions i've seen work
                best_found_version = version
        if best_found:
            verbose_print("find_java: Choosing %s (%s, compatible)" % (best_found,best_found_version))
            return best_found
        if first_found:
            verbose_print("find_java: Choosing %s (%s, possibly incompatible)" % (first_found,first_found_version))
            return first_found
        verbose_print("find_java: Giving up and choosing generic 'java'")
        return 'java' # just use the one in the path and pray

    # wrapper for subprocess.check_call to include timeout if and only if python version is 3.x (ugly hack to support python 2 and 3 at same time) [PY2]
    @staticmethod
    def my_check_call(args, stdin=None, stdout=None, stderr=None, shell=False, timeout=None):
        if sys.version_info[0]==2: # python 2.x has no timeout support [PY2]
            return subprocess.check_call(args,stdin=stdin,stdout=stdout,stderr=stdout,shell=shell)
        elif sys.version_info[0]==3:
            return subprocess.check_call(args,stdin=stdin,stdout=stdout,stderr=stdout,shell=shell,timeout=timeout)
        else:
            raise Exception("Unrecognized python version")

    @staticmethod
    def run_process(command_argv, output_file=None, input_file=None, timeout=None, shell=False):
        """
        Execute a shell command and return exit code, or -1 if the process launch failed.
            command_argv: The program name and its arguments, like C's argv
            output_file: file to write output (stdout+stderr), set to DEVNULL to discard, else it's not redirected
            input_file: file to read as stdin, omit to use the default stdin
            timeout: abort after the given delay (python3 only!)
        """
        cmd_str = "$ %s" % ' '.join(command_argv)

        # handle input_file, opening if needed
        if input_file is None:
            pass # nothing to do in this case
        elif isinstance(input_file,str) or type(output_file).__name__=="unicode":  # this ugly abomination courtesy of having to support python 2 and 3 [PY2]
            # given a filename, open it
            cmd_str += "  < %s" % input_file
            input_file = open(input_file, "r")
        elif hasattr(input_file, 'read'): 
            # given a readable file-like object
            cmd_str += "  < ..."
        else:
            raise IOError("Invalid input_file object: %s" % input_file)
        
        # handle output_file, opening if needed        
        if output_file is None:
            pass
        elif output_file is DEVNULL:
            cmd_str += "  >& /dev/null"
        elif isinstance(output_file,str) or type(output_file).__name__=="unicode":  # this ugly abomination courtesy of having to support python 2 and 3 [PY2]
            # given a filename, open it
            cmd_str += "  >& %s" % output_file
            output_file = open(output_file, "w")
        elif hasattr(output_file, 'write'): 
            # given a writable file-like object
            cmd_str += "  >& ..."
        else:
            raise IOError("Invalid output_file object: %s (%s)" % (output_file,type(output_file)))
            
        verbose_print(TextColors.BLUE + cmd_str + TextColors.END)
            
        try:
            return Utility.my_check_call(command_argv, stdout=output_file, stderr=output_file, stdin=input_file, timeout=timeout, shell=shell)
        except subprocess.CalledProcessError as exception:
            return exception.returncode
        except Exception as exception:
            if sys.version_info[0]==3 and isinstance(exception,subprocess.TimeoutExpired):
                # we do this ugly hack instead of just catching that exception type in order to support python 2 (god i can't want to get rid of python 2) [PY2]
                return EXITCODE_TIMEOUT
            else:
                print("run_process: %s" % exception)
                return -1

class Diff(object):
    """
    Encapsulates different ways of doing a diff between two files.
    """
    
    @staticmethod
    def apply_diff(diff_type, filename1, filename2, diff_filename):
        """
        Apply a named type of diff to the two files, with output going to the given diff_filename. Returns true on match.
        """
        if diff_type=='normal':
            return Diff.normal_diff(filename1, filename2, diff_filename)
        elif diff_type=='float':
            return Diff.float_diff(filename1, filename2, diff_filename)
        else:
            raise Exception("Unknown diff type: %s" % diff_type)
            
    @staticmethod
    def normal_diff(filename1, filename2, diff_filename):
        """
        Simple diff, using the standard utility. Ignores whitespace. Returns true on match.
        """
        command_argv = ["diff", "-bwB", filename1, filename2]
        exit_status = Utility.run_process(command_argv, output_file=diff_filename)
        return exit_status == 0

    @staticmethod
    def float_diff(filename1, filename2, diff_filename, frac_delta=0.001):
        """
        Float diff with tolerance. Returns true on match. File must be a list of token+float pairs (like a PizzaCalc or HoopStat output).
        """
        file1 = open(filename1, "r")
        file2 = open(filename2, "r")
        diff = open(diff_filename, "w")
        is_pass = True

        def line_match(line1, line2):
            if line1 == line2:
                return True
            match1 = re.match(r"(\w+)\s+([.\d]+)$", line1)
            if not match1:
                return False
            match2 = re.match(r"(\w+)\s+([.\d]+)$", line2)
            if not match2:
                return False
            key1 = match1.group(1)
            value1 = float(match1.group(2))
            key2 = match2.group(1)
            value2 = float(match2.group(2))
            if key1 != key2:
                return False
            if abs(frac_difference(value1, value2)) > frac_delta:
                return False
            return True

        # Fraction difference (i.e. percent difference but not x100) between two numbers
        # Special cases: if a=b=0, returns 0.0, if b=0 & a!=b, returns 1.0
        def frac_difference(num1, num2):
            if num2 == 0:
                if num1 == 0:
                    return 0.0
                else:
                    return 1.0
            return num1/num2 - 1.0

        for line1, line2 in zip_longest(file1, file2, fillvalue=""):
            line1 = line1.rstrip()
            line2 = line2.rstrip()
            if not line_match(line1, line2):
                diff.write("< %s\n> %s\n" % (line1, line2))
                is_pass = False

        file1.close()
        file2.close()
        diff.close()

        return is_pass


class CodeCheck:
    """
    Functions for running various penalty checks on code/circuits.
    """
    
    @staticmethod
    def logisim_check_disallowed(filename, penalty_info):
        """
        Check if disallowed component is used in Logisim circuit.
        
        Format of penalty_info is a list of penalty/component-lists. Specifically:
            [
              {
                "penalty": 0.25,
                "components": ["Adder","BitAdder",...],
                "ignore_subcircuits": ["memorylatch", ...]      # this field optional
              }, 
                 ...
            ]
            
        The harshest (lowest) penalty will be assessed if multiple violation types are encountered.
        
        Will ignore components in any subcircuit in list ignore_within_subcircuits, if provided.'
        
        Returns a (message, penalty) tuple if penalties need to be assessed, where message is a multiline string explaining what happened and penalty is the multiplier to be applied.
        Returns None if no penalties were assessed.
        """
        
        min_penalty = 1.0
        message = ""
        
        circ_components = Utility.logisim_get_components_used_per_circuit(filename)
        for pi in penalty_info:
            penalty = pi['penalty']
            disallowed_components = pi['components']
            ignore_subcircuits = pi.get('ignore_subcircuits',[])
            for subcircuit,component in circ_components:
                if subcircuit in ignore_subcircuits: 
                    continue
                if component in disallowed_components:
                    message += "%s: The '%s' subcircuit uses the '%s' component, which is disallowed.\n" % (filename, subcircuit, component)
                    min_penalty = min(penalty, min_penalty)

        if message:
            message += "Due to the above, the score will be multiplied by %.2f" % min_penalty
            return message, min_penalty
        else:
            return None

    @staticmethod
    def check_c_modulus_used(filename):
        """
        Attempt to find modulus operator use in C programs (doesn't fully parse, so can be fooled, but should be good enough).
        Returns true if it's found, else false.
        Quietly returns false if file can't be opened.
        """
        try:
            myFile = open(filename,"r")
            str1 = myFile.read() # slurp whole file
            myFile.close()
            str1 = re.sub('\".*\"'," ",str1) # eliminate quoted strings
            str1 = re.sub('//.*'," ",str1)  # eliminate one-line comments
            pattern = re.compile('/\\*.*?\\*/', flags=re.DOTALL) # eliminte multi-line comments
            str1 = re.sub(pattern," ",str1)
            return '%' in str1 # if % still remains, we're probably using it as mod operator
        except Exception as e:
            verbose_print("check_c_modulus_used: %s" % e)
            return False

    @staticmethod
    def check_c_math_h_used(filename):
        """
        Attempt to find #include <math.h> in C programs (doesn't fully parse, so can be fooled, but should be good enough).
        Returns true if it's found, else false.
        Quietly returns false if file can't be opened.
        """
        try:
            myFile = open(filename,"r")
            str1 = myFile.read() # slurp whole file
            myFile.close()
            str1 = re.sub('\".*\"'," ",str1) # eliminate quoted strings
            str1 = re.sub('//.*'," ",str1)  # eliminate one-line comments
            pattern = re.compile('/\\*.*?\\*/', flags=re.DOTALL) # eliminte multi-line comments
            str1 = re.sub(pattern," ",str1)
            return re.search(r'#include\s*<\s*math.h\s*>',str1) is not None # if #include<math.h> still remains
        except Exception as e:
            verbose_print("check_c_math_h_used: %s" % e)
            return False

class FileFilter(object):
    """
    Methods to filter output files. Allows easy composition of filters to do multiple things at once. 
    
    All filters are static methods that start with filter_ and take a file-like stream for input and yield lines of output like a file-like stream would.
    In other words, filter functions are file-in and file-out, like UNIX filters.
    
    Example usage:
    
        # see all filters available
        print(FileFilter.get_filters()) 
        
        # make a filter that does these steps in this order
        ff = FileFilter(['filter_x2y','filter_y2z','filter_remove_colon_prompts']) 
        
        # apply it in-place to a file, taking a backup
        ff.apply_to_file("thefile","thefile.orig") 
        
        # apply the filters live to a stream (note: the stream could be a file or even the result of applying another FileFilter)
        for line in ff.apply(stream): 
            # ...
    """
    
    def __init__(self, filter_list):
        """
        Take a list of filter functions as strings. They'll be applied in the order supplied when you call the apply_* methods.
        """
        self.filter_functions = []
        for filter_name in filter_list:
            self.filter_functions.append(self.get_filter_function_by_name(filter_name))
        
    @staticmethod
    def get_filters():
        """
        Inspect class's own functions to yield a list of valid filter functions.
        """
        return [funcname for funcname in FileFilter.__dict__ if funcname.startswith("filter_")]
        
    @staticmethod
    def get_filter_function_by_name(func_name):
        """
        Translate a string name of a filter function in this class to its underlying callable function.
        """
        return FileFilter.__dict__[func_name].__func__
        
    def apply(self,stream):
        """
        Accept a stream as input and apply all our filters to it, yielding a similar stream that can be read as an iterator line by line.
        """
        f = stream
        for func in self.filter_functions:
            f = func(f)
        return f
    
    def apply_to_file(self,filename, backup_filename=None):
        """
        Take a function that modifies a file stream's lines and apply it to edit the given file in-place, with an optional backup.
        """
        if backup_filename:
            shutil.copy(filename, backup_filename)
        fp_src = open(backup_filename, "r")
        fp_dst = open(filename, "w")
        for line in self.apply(fp_src):
            fp_dst.write(line)
        fp_src.close()
        fp_dst.close()

    @staticmethod
    def filter_logisim_strip_blank_probes(stream):
        """
        Remove the lines from logisim_cli output that describe blank probes. 
        This allows students to use probes for debugging without breaking the tester.
        """
        for line in stream:
            if not re.search(r'(probe         |/ )',line):
                yield line

    @staticmethod
    def filter_x2y(stream):
        """
        Small toy method to change the letter 'x' to 'y'. Just used for testing.
        """
        for line in stream:
            yield line.replace('x','y')

    @staticmethod
    def filter_y2z(stream):
        """
        Small toy method to change the letter 'y' to 'z'. Just used for testing.
        """
        for line in stream:
            yield line.replace('y','z')

    @staticmethod
    def filter_remove_colon_prompts(stream):
        """
        Remove content of lines up to and including a colon+whitespace; this removes colon-terminated prompts from interactive programs.
        Also removes blank lines. 
        
        Made to be used with interactive SPIM programs to hide colon prompts from output.
        """
        for line in stream:
            line = re.sub(r".*:[ \t]*", "", line)
            if re.search(r"\S", line):
                yield line
                
    @staticmethod
    def filter_spim(stream):
        """
        Filter out SPIM specific headers.
        """
        header_line_prefixes = [
            "SPIM Version",
            "Copyright 1990-",
            "All Rights",
            "See the file README",
            "Loaded:"
        ]
        for i, line in enumerate(stream):
            if i < len(header_line_prefixes) and any(line.startswith(prefix) for prefix in header_line_prefixes):
                continue
            yield line



class JSONWrapper(object):
    """
    Encapsulates JSON and, if a parent JSONWrapper object is provided, any key lookups will be applied to the parent if not found in this object.
    Useful to let JSON have hierarchical settings.
    """
    
    def __init__(self, json, parent=None):
        """
        Create a JSONWrapper.
            json: The dictionary or other structure returned from json.load or similar.
            parent: Another JSONWrapper object representing JSON that includes *this* object's JSON as a child.
        """
        self.json = json
        self.parent = parent
        
    # make [] lookups pull from json, and inherit to parent json on a miss
    def __getitem__(self,k):
        if self.parent is None:
            return self.json[k]
        else:
            if k in self.json:
                return self.json[k]
            else:
                return self.parent[k]
    def get(self,k,default):
        try:
            return self[k]
        except KeyError:
            return default
    def has(self,k):
        # safe way to see if we have the given key -- the usual '"blah" in obj' won't work because that doesnt tunnel parents
        try:
            v = self[k]
            return True
        except KeyError:
            return False
            
    # these other dict-alike methods taken from https://stackoverflow.com/questions/3387691/how-to-perfectly-override-a-dict
    def __setitem__(self,k,v):
        self.json[k] = v
    def __iter__(self):
        return iter(self.json)
    def __delitem__(self, key):
        del self.store[key]
    def __len__(self):
        return len(self.json)
        
    def __repr__(self):
        return str(self.json)
    __str__ = __repr__

class TestResult(object):
    """
    Encapsulates the result of a test execution.
    """
    
    def __init__(self, test, is_pass, points, message, error_flags):
        self.test = test # reference to the test object
        self.is_pass = is_pass
        self.points = points # will be None if this isnt the grader
        self.message = message # long form output string for use in gradescope result
        self.error_flags = error_flags # short form string tokens for use in tester stdout
        self.max_points = test.get("points",None) # will be None if this isnt the grader
        self.visibility = test.get("visibility","visible")
        
    def to_gradescope_dictionary(self):
        """
        Returns a dictionary appropriate for JSON-ifying and including in GradeScope's results.json
        """
        return {   
            "name": self.test.name,
            "score": self.points,
            "max_score": self.max_points,
            "output": self.message,
            "visibility": self.visibility
        }
        
    def get_console_line(self):
        """
        Returns a one-line string suitable for printing straight to the console
        """
        if self.is_pass:
            status = TextColors.GREEN + "Pass" + TextColors.END
        else:
            status = TextColors.RED + "Failed" + TextColors.END

        if self.error_flags:
            error_flag_str = TextColors.RED + " ".join(self.error_flags) + TextColors.END
        else:
            error_flag_str = ""
            
        if self.max_points is not None:
            scoring = "%0.2f/%0.2f" % (self.points, self.max_points)
            return "%-10s %-50s %-20s %-15s %s" % ("Test %d " % self.test.test_num, self.test['desc'], status, scoring, error_flag_str)
        else:
            return "%-10s %-50s %-20s %s" % ("Test %d " % self.test.test_num, self.test['desc'], status, error_flag_str)

class TestResultSet(object):
    """
    Encapsulates the result of running a number of test suites. Meant to be created, then appended to with test results 
    (via .add_result()) and top-level messages (via .append_message()).
    
    Two TestResultSets can be added together, combining their test results, message, etc.
    
    Once built, you can do get_points(), get_max_points(), and generate_gradescope_results().
    """
    
    def __init__(self, test_results=None, message="", elapsed_time=0):
        self.test_results = iff(test_results is None,[],test_results) # array of TestResult objects, one for each test run
        self.message = message # to be included in top-level output in the gradescope results
        self.elapsed_time = elapsed_time # to be included in gradescope results
        
    def __add__(self, other):
        """
        Allow concatenation of two TestResultSet objects -- this lets us combine results for multiple suites.
        """
        return TestResultSet(self.test_results + other.test_results, self.message + other.message, self.elapsed_time + other.elapsed_time)
        
    def add_result(self, test_result):
        """
        Add a test result to this set.
        """
        self.test_results.append(test_result)
        
    def set_elapsed_time(self, elapsed_time):
        """
        Update the elapsed time.
        """
        self.elapsed_time = elapsed_time
        
    def apply_penalty(self, penalty):
        """
        Multiply all scores in our test_results by the given factor.
        """
        for tr in self.test_results:
            if tr.points is not None:
                tr.points *= penalty # apply penalty
        
    def append_message(self, message):
        """
        Add to the top-level message included in GradeScope results.
        """
        self.message += message
        
    def get_points(self):
        """
        Returns the total achieved points from the tests.
        """
        return sum(tr.points for tr in self.test_results)
        
    def get_max_points(self):
        """
        Returns the total available points from the tests.
        """
        return sum(tr.max_points for tr in self.test_results)
        
    def generate_gradescope_results(self, json_filename="results.json", compile_output_filename="compile_output.txt"):
        """
        Generate a results.json compatible with GradeScope. Incorporates test results as well as a 
        top-level message that includes the append_message provided at object creation time. Also folds in
        compiler output from a given text file, if available.
        """
        
        # top level message for gradescope
        message = GRADESCOPE_MESSAGE_HEADER
        
        # include compile output in gradescope message if present
        if compile_output_filename is not None and os.path.exists(compile_output_filename):
            with open(compile_output_filename, "r") as compile_output_file:
                compile_output = compile_output_file.read()
            message += "\n\n" + "###### COMPILE OUTPUT ######\n" + compile_output
            
        message += self.message
        
        # this is the top-level json for gradescope; it incorates the individual test result jsons
        gradescope_result = {
            "score": self.get_points(),
            "stdout_visibility": "hidden",
            "output": message,
            "tests": [tr.to_gradescope_dictionary() for tr in self.test_results],
            "execution_time": self.elapsed_time
        }

        # write it
        with open(json_filename, "w+") as result_file:
            json.dump(gradescope_result, result_file, indent=2, separators=(',', ': '))

class PrereqMissing(Exception): 
    """
    Special exception class for when a pre-req to a test execution is missing (like missing the executable, the spim tool, etc.)
    """
    pass

class Test(JSONWrapper):
    """
    Encapsulates a single test, i.e. the one element in the settings['test_suites'][suite_name]['tests'] list.
    It's parent is its TestSuite.
    """
    def __init__(self, suite, test_num):
        super(Test,self).__init__(suite.json['tests'][test_num], parent=suite)
        self.suite = suite
        self.test_num = test_num
        
        self.name = "%s test %d: %s" % (self.suite.name, self.test_num, self['desc'])
        
    def __repr__(self):
        return "Test '%s' {%s}" % (self.name, ", ".join("%s: %s" %(k,v) for k,v in self.json.items()))
    __str__ = __repr__
    
    def get_command(self):
        """
        Returns a tuple of the full argv of the command, including the base command (argv[0]) and all arguments after the command it (argv[1:])
        """
        mode = self.suite['mode']
        if mode == "exe":
            return [self.suite.get_target()] + self['args']
        elif mode == "java":
            return [Utility.find_java(), self.suite.get_target()] + self['args']
        elif mode == "spim":
            return [self['spim_command'], "-f", self.suite.get_target()] # Note: "args" field is not used in this mode
        elif mode == "logisim":
            return [Utility.find_java(), "-jar", self['logisim_jar'], "-f", self.suite.get_target()] + self['args']
        else:
            raise Exception("Internal error determining test target")
    
    def check_prereq_missing(self, include_valgrind_check=False):
        """
        Raises a PrereqMissing exception if a key ingredient is missing.
        """
        mode = self.suite['mode']
        
        # ensure java if needed
        if mode in ("java","logisim"):
            java = Utility.find_java()
            if not Utility.verify_executable(java,use_path=True):
                raise PrereqMissing("Missing java interpreter -- install JVM 1.6/1.7/1.8 ('sudo apt install openjdk-8-jre' on Ubuntu Linux).")
                
        if mode == "exe":
            if not Utility.verify_executable(self.suite.get_target(), use_path=False):
                raise PrereqMissing("Missing executable: %s -- did you forget to compile?" % self.suite.get_target())
        elif mode == "java": 
            classfile = "%s.class" % self.suite.get_target()
            if not os.path.isfile(classfile):
                raise PrereqMissing("Missing class file: %s -- did you forget to compile?" % classfile)
        elif mode == "spim":
            if not Utility.verify_executable(self['spim_command'],use_path=True):
                raise PrereqMissing("Missing command-line spim -- install it ('sudo apt install spim' on Ubuntu Linux)")
            if not os.path.isfile(self.suite.get_target()):
                raise PrereqMissing("Missing program: %s" % self.suite.get_target())
        elif mode == "logisim":
            if not os.path.isfile(self.suite.get_target()):
                raise PrereqMissing("Missing circuit: %s" % self.suite.get_target())
        else:
            raise Exception("Internal error checking prereqs -- invalid mode")
        
        global has_valgrind
        if has_valgrind and include_valgrind_check and not Utility.verify_executable("valgrind",True):
            has_valgrind = False
            print(TextColors.RED + "Missing valgrind tool -- install it ('sudo apt install valgrind' on Ubuntu Linux)\n\
The tests below will skip the valgrind checks.\n\
You should test on a platform with valgrind before turning this in!" + TextColors.END)

        
    # filenames for the expected/generated files associated with this test
    def expected_output_filename(self):         return os.path.join(self['test_dir'], "%s_expected_%d.txt" % (self.suite.name, self.test_num))
    def actual_output_filename(self):           return os.path.join(self['test_dir'], "%s_actual_%d.txt" % (self.suite.name, self.test_num))
    def actual_output_backup_filename(self):    return "%s.orig" % self.actual_output_filename()
    def diff_filename(self):                    return os.path.join(self['test_dir'], "%s_diff_%d.txt" % (self.suite.name, self.test_num))

    def execute(self, add_valgrind=False, suppress_output=False):
        """
        Execute a test, write output to usual files, return exitcode. 
        If add_valgrind is true, run with valgrind (in which case exitcode will be EXITCODE_VALGRIND_ERROR if valgrind reported an issue).
        If suppress_output is true, then the usual stdout redirect will be disabled.
        """
        
        self.check_prereq_missing(include_valgrind_check=add_valgrind) # raise exception if we dont have the files we need
        
        command_argv = self.get_command()
        if has_valgrind and add_valgrind:
            command_argv = ["valgrind","-q","--error-exitcode=%d" % EXITCODE_VALGRIND_ERROR,"--show-reachable=yes","--leak-check=full"] + command_argv
        
        if suppress_output:
            output_file = DEVNULL
        else:
            output_file = self.actual_output_filename()
            
        # actually run it!
        exitcode = Utility.run_process(command_argv, output_file=output_file, input_file=self.get('stdin',None), timeout=self['timeout'])
        
        # apply filters to output if requested
        if self.has('output_filters') and not suppress_output:
            ff = FileFilter(self['output_filters'])
            try:
                ff.apply_to_file(self.actual_output_filename(), self.actual_output_backup_filename())
            except UnicodeDecodeError:
                with open(self.actual_output_filename(), "w") as file:
                    print("UNICODE DECODE ERROR WHEN READING FILE! Check your program output for any <?> characters.", file=file)
            
        return exitcode
        
    def run(self):
        """
        Run a specific test case. Returns as TestResult object.
        """
        
        diff_type = self.get("diff", "normal") # default "normal"
        max_points = self.get("points",None) # this being None is how we tell if this is the grader or not in here
        
        is_pass = True
        penalty = 1.0 # base penalty rate
        error_flags = [] # text flags will be collected here to annotate failure
        
        # run it!
        exitcode = self.execute()
        message = ""
        
        # complain about timeout or other bad exitcode
        if exitcode == EXITCODE_TIMEOUT:
            # no penalty for timing out (but odds of passing the output match with a timeout are very low)
            error_flags.append("timed_out")
            message += "Test timed out after %d seconds!\n" % self['timeout']
        elif exitcode != 0:
            is_pass = False
            if exitcode == EXITCODE_SEGFAULT:
                error_flags.append("segfault") # same penalty, but we label segfaults to make it clearer to students
                message += "Segfault detected!\n"
            else:
                error_flags.append("exitcode_nonzero")
                message += "Exit status was nonzero (%d)!\n" % exitcode
            
            if self.has('penalty_exitcode_nonzero'):
                penalty *= self['penalty_exitcode_nonzero']
                message += "  ^ Test score will be multiplied by %.2f.\n" % self['penalty_exitcode_nonzero']
        
        # run diff!
        try:
            was_diff_ok = Diff.apply_diff(diff_type, self.expected_output_filename(), self.actual_output_filename(), self.diff_filename())
        except UnicodeDecodeError:
            was_diff_ok = False
            error_flags.append("invalid_output")
            message += "Unicode decode error in output!\n"
        
        # complain about diff mismatch
        if not was_diff_ok:
            is_pass = False
            penalty = 0 # no credit for failed test
            error_flags.append("output_differs")
            message += "The actual output did not match the expected output!\n"
            
            message += "\n###### DIFF ######\n"
            try:
                with open(self.diff_filename(),"r") as fp:
                    content = fp.read(OUTPUT_MAX_BYTES)
                    was_truncated = fp.read(1) != '' # if we can read another byte, than the first read didnt get it all
                    if was_truncated:
                        message += "\n###### The diff was truncated for being too long -- infinite loop?\n"
                    message += content
            except Exception as e: 
                message += "\n###### Error: the diff could not be read: %s\n" % e
                
            message += "\n###### ACTUAL ######\n"
            try:
                with open(self.actual_output_filename(),"r") as fp:
                    content = fp.read(OUTPUT_MAX_BYTES)
                    was_truncated = fp.read(1) != '' # if we can read another byte, than the first read didnt get it all
                    if was_truncated:
                        message += "\n###### The actual output was truncated for being too long -- infinite loop?\n"
                    message += content
            except Exception as e: 
                message += "\n###### Error: the actual output could not be read: %s\n" % e

        # if requested, run it again with valgrind
        if self.has("penalty_valgrind"):
            exitcode_with_valgrind = self.execute(add_valgrind=True, suppress_output=True)
            if exitcode_with_valgrind==EXITCODE_VALGRIND_ERROR:
                is_pass = False
                penalty *= self["penalty_valgrind"]
                error_flags.append("valgrind_error")
                message += "Valgrind memory error detected! (Test score will be multiplied by %.2f)\n" % (self["penalty_valgrind"])
        
        # if i'm the grader, compute points
        if max_points is not None:
            points = max_points*penalty
        else:
            points = None
        
        # compile result into an object
        result = TestResult(test=self, is_pass=is_pass, points=points, message=message, error_flags=error_flags)
            
        return result
        
    def bless(self):
        """
        Bless the results of this test (rename actual -> expected).
        """
        src  = self.actual_output_filename()
        dest = self.expected_output_filename()
        verbose_print("Rename %s -> %s" % (src,dest))
        os.rename(src,dest)
    

class Suite(JSONWrapper):
    """
    Encapsulates a test suite, i.e. settings['test_suites'][suite_name].
    Its parent is the top-level test settings as represented by a Tester object.
    """
    def __init__(self, tester, name):
        super(Suite,self).__init__(tester.json['test_suites'][name], parent=tester)
        self.tester = tester
        self.name = name
        
        self.tests = []
        for test_num in range(len(self.json['tests'])):
            self.tests.append(Test(self, test_num))
            
    # shell globs for the various files associated with this suite (used for the clean and bless functions)
    def expected_output_filename_mask(self): return os.path.join(self['test_dir'], "%s_expected_*.txt" % (self.name))
    def actual_output_filename_mask(self):   return os.path.join(self['test_dir'], "%s_actual_*.txt*" % (self.name))
    def diff_filename_mask(self):            return os.path.join(self['test_dir'], "%s_diff_*.txt" % (self.name))
    
    def get_target(self):
        """
        Based on either the 'target' override parameter or the name+mode of the test suite, determine what filename we're doing stuff to,
        e.g. "./suitename" (executable), "./suitename.s" (spim), etc.
        """
        mode = self['mode']
        if self.has('target'): 
            return self['target']
        elif mode == "exe":
            return "./%s" % self.name
        elif mode == "java":
            return self.name
        elif mode == "spim":
            return "%s.s" % self.name
        elif mode == "logisim":
            return "%s.circ" % self.name
        else:
            raise Exception("Internal error determining test target")
            
    def check_suite_level_penalties(self):
        """
        Apply penalty checks that work at the suite level (e.g., code checks).
        
        Returns a (message, penalty) tuple if penalties need to be assessed, where message is a multiline string explaining what happened and penalty is the multiplier to be applied.
        Returns None if no penalties were assessed.
        """
        penalty = 1.0 # default to no penalty, apply losses consecutively
        message = ""
        
        # check for penalty_logisim_disallowed_components
        # (see Utility.logisim_check_disallowed for info on json format)
        
        if self.has('penalty_logisim_disallowed_components'):
            penalty_info = self['penalty_logisim_disallowed_components']
            target = self.get_target()
            r = CodeCheck.logisim_check_disallowed(target, penalty_info)
            verbose_print("%s: Checking for disallowed logisim components" % target)
            if r:
                this_message, this_penalty = r
                penalty *= this_penalty
                message += "%s\n" % this_message
            
        # Check for 'simple' penalties of the form: { penalty: PENALTY, file: FILE }
        
        if self.has('penalty_c_math_or_modulo'):
            penalty_info = self['penalty_c_math_or_modulo']
            this_penalty = penalty_info['penalty']
            target = penalty_info['file']
            verbose_print("%s: Checking for modulo and math.h" % target)
            if CodeCheck.check_c_modulus_used(target):
                penalty *= this_penalty
                message += "%s: It appears that modulo was used; this will multiply the score by %.2f\n" % (target, this_penalty)
            elif CodeCheck.check_c_math_h_used(target):
                penalty *= this_penalty
                message += "%s: It appears that math.h was included; this will multiply the score by %.2f\n" % (target, this_penalty)

        if self.has('penalty_c_modulo'):
            penalty_info = self['penalty_c_modulo']
            this_penalty = penalty_info['penalty']
            target = penalty_info['file']
            verbose_print("%s: Checking for modulo" % target)
            if CodeCheck.check_c_modulus_used(target):
                penalty *= this_penalty
                message += "%s: It appears that modulo was used; this will multiply the score by %.2f\n" % (target, this_penalty)
        
        if message:
            return message, penalty
        else:
            return None

    def run(self):
        """
        Run a test suite. Returns an TestResultSet object.
        """
        print("Running tests for %s..." % (self.name))
        
        start_time = time.time()
        
        test_result_set = TestResultSet()
        for test in self.tests:
            try:
                result = test.run()
                print(result.get_console_line())
                test_result_set.add_result(result)
            except PrereqMissing as e:
                print(TextColors.RED + str(e) + TextColors.END)
                message_decorated = ("!"*80 + "\n") + "ERROR: %s\n"%str(e) + ("!"*80 + "\n")
                test_result_set.append_message(message_decorated)
                return test_result_set # abort the whole suite if we were missing a pre-req
                
        r = self.check_suite_level_penalties()
        if r:
            message, penalty = r
            test_result_set.apply_penalty(penalty)
            message_decorated = ("!"*80 + "\n") + message + ("!"*80 + "\n")
            print(TextColors.RED + message_decorated + TextColors.END)
            test_result_set.append_message(message_decorated)

        print("Done running tests for %s.\n" % (self.name))
        
        test_result_set.set_elapsed_time(time.time() - start_time)

        return test_result_set
    
    def clean(self, echo=False):
        """
        For this suite, 'clean' (remove actual+diff). Returns number of files actually deleted.
        Removes files by mask rather than by specific test, so it will clean even if more actual+diff files are around (e.g. if you're editing the settings between runs).
        If the echo argument is true, status info is printed as we go.
        """
        n = 0
        if echo:
            print("Removing %s %s" % (self.actual_output_filename_mask(), self.diff_filename_mask()))
        for filename in glob.glob(self.actual_output_filename_mask()) + glob.glob(self.diff_filename_mask()):
            verbose_print("Removing %s" % filename)
            os.remove(filename)
            n+=1
        #Utility.run_process(['echo','Qrm',self.actual_output_filename_mask(), self.diff_filename_mask()], shell=True)
        return n
        
    def bless(self, echo=False):
        """
        For this suites, 'bless' all the results (convert actual -> expected).
        If the echo argument is true, status info is printed as we go.
        """
        if echo:
            print("%s: Clearing old 'expected' files: %s" % (self.name, self.expected_output_filename_mask()))
        for filename in glob.glob(self.expected_output_filename_mask()):
            verbose_print("Removing %s" % filename)
            os.remove(filename)
            
        if echo:
            print("%s: Converting 'actual' to 'expected'" % self.name)
        for test in self.tests:
            test.bless()
        
    def __repr__(self):
        r = "Suite '%s' (%d tests):\n" % (self.name, len(self.tests))
        for test in self.tests:
            r += "  %s\n" % str(test)
        return r
    __str__ = __repr__

class Tester(JSONWrapper):
    """
    Externally, eats JSON and does tests.
    
    Internally, it encapsulates settings JSON, but promotes test suites and tests to be objects.
    Attributes of suites and their tests are looked up recursively, so a test can have a different timeout from a suite; and a suite can differ from the global settings.
    
    Use this object like a regular dictionary, except with the .suites['SUITENAME'] attribute.
    Similarly, suites themselves have .tests[NUMBER] attribute.
    
    Some examples:
    
        tester = Tester("tests")
        print(tester['mode'])
        for suite_name,suite in tester.suites.items():
            for test in suite.tests:
                print(test)
                print(test['timeout'])
        print(tester.suites['byseven'].tests[0]['timeout'])
    
    """
    
    def __init__(self, test_dir):
        # start with default settings
        settings_json = OrderedDict(SETTINGS_DEFAULT)
        settings_json['test_dir'] = test_dir # inject the test_dir in the json so our child objects can find it easily
        
        # read settings json
        settings_path = os.path.join(test_dir,SETTINGS_FILENAME)
        with open(settings_path, "r") as sfile:
            settings_json.update(json.load(sfile, object_pairs_hook=OrderedDict)) # OrderedDict keeps dicts in read-order
        
        # parent class constructor eats the json
        super(Tester,self).__init__(settings_json)
        
        # validate settings
        for s in ['mode','test_suites']:
            if s not in settings_json:
                raise KeyError("SETTINGS ERROR: Missing item: %s" % s)
        if settings_json['mode'] not in VALID_TEST_MODES:
            raise ValueError("SETTINGS ERROR: Invalid mode: %s" % settings['mode'])
        
        # build the suite objects
        self.suites = OrderedDict()
        for suite_name in self.json['test_suites']:
            self.suites[suite_name] = Suite(self, suite_name)
    
    def run_suites(self, suite_names):
        """
        Run a set of test suites and return a list of their results.
        """
        
        test_result_set = TestResultSet() # start with an empty set of results and add in the suite results
        for suite in self.each_suite(suite_names):
            test_result_set += suite.run()
            
        return test_result_set
        
    def clean_suites(self, suite_names, echo=False):
        """
        For each of the named suites, 'clean' (remove actual+diff). Returns number of files actually deleted.
        If the echo argument is true, status info is printed as we go.
        """
        n=0
        for suite in self.each_suite(suite_names):
            n += suite.clean(echo=echo)
        return n
     
    def bless_suites(self, suite_names, echo=False):
        """
        For each of the named suites, 'bless' the results (convert actual -> expected).
        If the echo argument is true, status info is printed as we go.
        """
        for suite in self.each_suite(suite_names):
            suite.bless(echo=echo)
     
    def each_suite(self, suite_names=None):
        """
        Iterate the suites in this tester, either by names (if provided) or just all of them.
        """
        if suite_names is None:
            suite_names = self.suites.keys()
        for suite_name in suite_names:
            yield self.suites[suite_name]
     
    def __repr__(self):
        r = "Tester:\n"
        for k,v in self.json.items():
            if k=='test_suites': continue
            r += "  %s: %s\n" % (k,v)
        r += "  test_suites (%d suites):\n" % (len(self.suites))
        for suite_name,suite in self.suites.items():
            r += indent(str(suite),4)
        return r
    __str__ = __repr__

def main():
    """
    Parse arguments and run auto-tester/grader.
    """
    global verbose

    test_dir = DEFAULT_TEST_DIR # the default for the student auto-tester; to be changed with -t if you want the instructor auto-grader
    
    # Allow manual override of test directory with "-t <test_dir>" -- this is done outside of argparse, since argparse needs settings to present a good help message
    if len(sys.argv) >=3 and "-t" in sys.argv:
        idx = sys.argv.index('-t') # find the -t
        sys.argv.pop(idx) # lose the -t itself
        test_dir = sys.argv.pop(idx) # pop out the test directory argument
        
    # create the tester!
    tester = Tester(test_dir)
    
    is_grader = tester.get('is_grader',False)
    
    # argument setup
    parser = argparse.ArgumentParser(description=iff(is_grader,"Instructor auto-grader version %s." % VERSION,"Student auto-tester version %s." % VERSION))
    parser.add_argument("test_suite", metavar='<SUITE_NAME>', choices=['ALL']+list(tester['test_suites'].keys()), help="A test suite name to run (%s), or 'ALL' for all of them." % ', '.join("'%s'" % s for s in tester['test_suites'].keys()))
    parser.add_argument('-C', '--clean', action='store_true', help="Remove generated actual and diff files for chosen suite(s).")
    parser.add_argument('-G', '--generate-expected', help=argparse.SUPPRESS, action='store_true') # not for common use! assumes program is correct and uses it to generate the expected outputs
    #parser.add_argument_group('group')
    parser.add_argument('--mode', help=argparse.SUPPRESS, type=str, default=None) # Override default mode specified by settings file
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose mode. Shows the commands executed.")
    parser.add_argument('-t', dest="test_dir", metavar="TESTDIR", type=str, help="Choose the directory with the "+DEFAULT_TEST_DIR+" and test content. Default: %(default)s", default=DEFAULT_TEST_DIR)
    # ^ Note: we don't actually *use* this parser option, as it's manually pulled out before the parser is created (see earlier in this function). It's here so the help message includes it. 
    if is_grader:
        parser.add_argument('-e', '--extra-credit-multiplier', metavar='M', help='Multiply the total score by the given value.', type=float, default=None) 
        

    # argpase is very restrictive - if it doesn't get a test_suite, it prints a robo-generated error message that's not very helpful
    # we catch the case of no arguments given and print a nice error instead
    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    # apply command line mode override
    if args.mode:
        tester['mode'] = args.mode
    verbose = args.verbose
    
    # figure out the suite(s) to do (or do the special clean mode)
    if args.test_suite == 'ALL':
        suite_names = tester.suites.keys()
    else:
        suite_names = [args.test_suite]
    
    # handle special behavior-changing modes like --clean, etc.:
    if args.clean:
        print("Cleaning up actual+diff files...")
        num_files_removed = tester.clean_suites(suite_names, echo=True)
        print("Files removed: %d" % num_files_removed)
        return # stop here
        
    # actually run the tests!
    test_result_set = tester.run_suites(suite_names)
    
    # extra credit multiplier
    if is_grader and args.extra_credit_multiplier:
        print(TextColors.GREEN + "** Applying the requested extra credit multiplier of %.2f **"%args.extra_credit_multiplier + TextColors.END)
        test_result_set.apply_penalty(args.extra_credit_multiplier)
    
    # generate expected results by "blessing" the results generated just now (rename actual -> expected)
    if args.generate_expected:
        print(TextColors.GREEN + "** Converting actual results to expected! **" + TextColors.END)
        tester.bless_suites(suite_names, echo=True)
        return # stop here
        
    # generate gradescope result json
    if is_grader:
        test_result_set.generate_gradescope_results()
            
        print("Done. Score: %.2f / %.2f" % (test_result_set.get_points(), test_result_set.get_max_points()))
        print("")

if __name__ == "__main__":
    main()

