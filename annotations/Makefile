# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Builds the j2objc annotations as a .jar file.
#
# Author: Tom Ball, Keith Stanger

J2OBJC_ROOT = ..

include ../make/common.mk
include classes.mk

JAR_NAME = j2objc-annotations-3.0.0-oracle-00001.jar
JAR = $(BUILD_DIR)/$(JAR_NAME)
DIST_JAR = $(DIST_JAR_DIR)/$(JAR_NAME)

CLASSES_DIR = $(BUILD_DIR)/classes
JAVA_SOURCE_DIR = src/main/java
JAVA9_CLASSES_DIR = $(BUILD_DIR)/classes-java9
JPMS_CLASS = $(JAVA9_CLASSES_DIR)/module-info.class

SOURCE_JAVA_FULL = $(ANNOTATION_SOURCE_JAVA:%=$(JAVA_SOURCE_DIR)/%)
SOURCE_JAVA9_MODULE = $(ANNOTATION_MODULE_INFO:%=$(JAVA_SOURCE_DIR)/%)

$(BUILD_DIR) $(CLASSES_DIR) $(JAVA9_CLASSES_DIR) $(DIST_JAR_DIR):
	@mkdir -p $@

$(JPMS_CLASS):
	@echo Building j2objc annotations JPMS module
	@$(JAVAC) -sourcepath $(JAVA_SOURCE_DIR) -encoding UTF-8 --release 9 -d $(JAVA9_CLASSES_DIR) \
		-nowarn $(SOURCE_JAVA9_MODULE)
	@rm -fr $(JAVA9_CLASSES_DIR)/com

$(JAR): $(SOURCE_JAVA_FULL) | $(BUILD_DIR) $(CLASSES_DIR) $(JAVA9_CLASSES_DIR) $(JPMS_CLASS)
	@echo Building j2objc annotations
	@$(JAVAC) -encoding UTF-8 -d $(CLASSES_DIR) -source 1.8 -target 1.8 \
	    -nowarn $^
	@jar cf $(JAR) -C $(CLASSES_DIR) . --release 9 -C $(JAVA9_CLASSES_DIR) .

$(DIST_JAR): $(JAR) | $(DIST_JAR_DIR)
	@install -m 0644 $< $@

dist: $(DIST_JAR)
	@:
	@mvn -DnewVersion="3.0.0-oracle-00001" -DprocessAllModules=true versions:set --settings settings.xml
	@mvn clean install -Dgpg.skip --settings settings.xml
	@mvn -Durl=https://artifactory.oci.oraclecorp.com/bfs-dev-generic-local/non-validated/2890f024-fad0-4c7d-b13e-158aacf474fg_1 -DrepositoryId=releases -DpomFile=pom.xml -Dfile=build_result/j2objc-annotations-3.0.0-oracle-00001.jar -Dfiles=target/j2objc-annotations-3.0.0-oracle-00001-javadoc.jar,target/j2objc-annotations-3.0.0-oracle-00001-sources.jar -Dtypes=jar,jar -Dclassifiers=sources,javadoc -Pcompliant-profile --settings settings.xml  org.apache.maven.plugins:maven-deploy-plugin:3.1.4:deploy-file

clean:
	@rm -rf $(BUILD_DIR) $(DIST_JAR)
