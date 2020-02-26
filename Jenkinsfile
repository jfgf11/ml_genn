#!groovy​

//--------------------------------------------------------------------------
// Helper functions
//--------------------------------------------------------------------------

// Wrapper around setting of GitHUb commit status curtesy of https://groups.google.com/forum/#!topic/jenkinsci-issues/p-UFjxKkXRI
// **NOTE** since that forum post, stage now takes a Closure as the last argument hence slight modification 
void buildStage(String message, Closure closure) {
    stage(message) {
        try {
            setBuildStatus(message, "PENDING");
            closure();
        }
	catch (Exception e) {
            setBuildStatus(message, "FAILURE");
        }
    }
}

void setBuildStatus(String message, String state) {
    // **NOTE** ManuallyEnteredCommitContextSource set to match the value used by bits of Jenkins outside pipeline control
    step([
        $class: "GitHubCommitStatusSetter",
        reposSource: [$class: "ManuallyEnteredRepositorySource", url: "https://github.com/genn-team/genn/"],
        contextSource: [$class: "ManuallyEnteredCommitContextSource", context: "continuous-integration/jenkins/branch"],
        errorHandlers: [[$class: "ChangingBuildStatusErrorHandler", result: "UNSTABLE"]],
        statusResultSource: [ $class: "ConditionalStatusResultSource", results: [[$class: "AnyBuildResult", message: message, state: state]] ]
    ]);
}


//--------------------------------------------------------------------------
// Entry point
//--------------------------------------------------------------------------

// All the types of build we'll ideally run if suitable nodes exist
def desiredBuilds = [
    ["cpu_only", "linux", "x86_64", "python27"] as Set,
    ["cpu_only", "linux", "x86_64", "python3"] as Set,
    ["cuda10", "linux", "x86_64", "python27"] as Set,
    ["cuda10", "linux", "x86_64", "python3"] as Set,
    ["cpu_only", "mac", "python27"] as Set,
    ["cpu_only", "mac", "python3"] as Set
]

// Build dictionary of available nodes and their labels
def availableNodes = [:]
for (node in jenkins.model.Jenkins.instance.nodes) {
    if (node.getComputer().isOnline() && node.getComputer().countIdle() > 0) {
        availableNodes[node.name] = node.getLabelString().split() as Set
    }
}

// Add master if it has any idle executors
if (jenkins.model.Jenkins.instance.toComputer().countIdle() > 0) {
    availableNodes["master"] = jenkins.model.Jenkins.instance.getLabelString().split() as Set
}

// Loop through the desired builds
def builderNodes = []
for (b in desiredBuilds) {
    // Loop through all available nodes
    for (n in availableNodes) {
        // If, after subtracting this node's labels, all build properties are satisfied
        if ((b - n.value).size() == 0) {
            // Add node's name to list of builders and remove it from dictionary of available nodes
            // **YUCK** for some reason tuples aren't serializable so need to add an arraylist
            builderNodes.add([n.key, n.value])
            availableNodes.remove(n.key)
            break
        }
    }
}

//  desiredBuilds:  list of desired node feature sets
// availableNodes:  dict of node feature sets, keyed by node name
//   builderNodes:  list of [node_name, node_features] satisfying desiredBuilds entries


//--------------------------------------------------------------------------
// Parallel build step
//--------------------------------------------------------------------------

// **YUCK** need to do a C style loop here - probably due to JENKINS-27421 
def builders = [:]
for (b = 0; b < builderNodes.size(); b++) {
    // **YUCK** meed to bind the label variable before the closure - can't do 'for (label in labels)'
    def nodeName = builderNodes.get(b).get(0)
    def nodeLabel = builderNodes.get(b).get(1)
   
    // Create a map to pass in to the 'parallel' step so we can fire all the builds at once
    builders[nodeName] = {
        node(nodeName) {
            stage("Checkout (${NODE_NAME})") {
		// Checkout Tensor GeNN
                echo "Checking out Tensor GeNN";
                sh "rm -rf tensor_genn";
		checkout scm
            }

	    buildStage("Setup virtualenv (${NODE_NAME})") {
		// Set up new virtualenv
		echo "Creating virtualenv";
		sh """
                    pip install virtualenv
                    rm -rf ${WORKSPACE}/venv
                    virtualenv ${WORKSPACE}/venv
                    source ${WORKSPACE}/venv/bin/activate
                    pip install -U pip
                    pip install tensorflow>2.0 pytest pytest-cov
                """
	    }

            buildStage("Installing PyGeNN (${NODE_NAME})") {
		// Checkout GeNN
		echo "Checking out GeNN";
		sh "rm -rf genn";
		sh "git clone --branch tensor_genn https://github.com/genn-team/genn.git";

		dir("genn") {
		    // Build dynamic LibGeNN
		    echo "Building LibGeNN";
		    def messages_libGeNN = "libgenn_build_${NODE_NAME}";
		    def commands_libGeNN = """
                        rm -f ${messages_libGeNN}
                        make DYNAMIC=1 LIBRARY_DIRECTORY=`pwd`/pygenn/genn_wrapper/ 1>\"${messages_libGeNN}\" 2>&1
                    """;
		    def status_libGeNN = sh script:commands_libGeNN, returnStatus:true;
		    if (status_libGeNN != 0) {
			setBuildStatus("Building PyGeNN (${NODE_NAME})", "FAILURE");
		    }
		    archive messages_libGeNN;

		    // Build PyGeNN module
		    echo "Building and installing PyGeNN";
		    def messages_PyGeNN = "pygenn_build_${NODE_NAME}";
		    def commands_PyGeNN = """
                        source ${WORKSPACE}/venv/bin/activate
                        rm -f ${messages_PyGeNN}
                        python setup.py clean --all
                        python setup.py install 1>\"${messages_PyGeNN}\" 2>&1
                        python setup.py install 1>\"${messages_PyGeNN}\" 2>&1
                    """;
		    def status_PyGeNN = sh script:commands_PyGeNN, returnStatus:true;
		    if (status_PyGeNN != 0) {
			setBuildStatus("Building PyGeNN (${NODE_NAME})", "FAILURE");
		    }
		    archive messages_PyGeNN;
		}
            }

            buildStage("Running tests (${NODE_NAME})") {
                dir("tensor_genn") {
		    // Set up new virtualenv
		    echo "Installing Tensor GeNN";
		    sh """
                        source ${WORKSPACE}/venv/bin/activate
                        pip install .
                    """

		    dir("tests") {
			// Generate unique name for message
			def messages_tests = "test_output_${NODE_NAME}";

			// Run test suite
			def commands_tests = """
                            source ${WORKSPACE}/venv/bin/activate
                            pytest -v 1>\"${messages_tests}\" 2>&1
                        """;
			def status_tests = sh script:commands_tests, returnStatus:true;
			if (status_tests != 0) {
			    setBuildStatus("Running tests (${NODE_NAME})", "UNSTABLE");
			}
			archive messages_tests;
		    }
		}
	    }
        }
    }
}

// Run builds in parallel
parallel builders;