import requests
import os
import sys
import tomli
from artifactory import ArtifactoryPath
from artifactory import ArtifactoryException
import pathlib
import subprocess
import filecmp
import shutil
from time import gmtime, strftime
from yattag import Doc, indent
import oci
import re
import platform
from atlassian import Confluence
from bs4 import BeautifulSoup
import base64


pathTestToml = "pom.properties.toml"

class ParseToml():
    def __init__(self, pathToTomlFile):
        self.tomlParsed = None
        try:
            with open(pathToTomlFile, 'r') as tomlPomProperties:
                tomlObject = tomli.loads(tomlPomProperties.read())
                self.tomlParsed = tomlObject
        except Exception as e:
            print ("Error: failed to parse the toml file ", pathToTomlFile)

class ConfluenceHandler():
    def __init__(self) -> None:
        self.conf_token = os.getenv("CONFLUENCE_TOKEN")
        if self.conf_token == None:
            print ("Error: couldn't find the confluence token")
            sys.exit(1)

        self.conf_site = "https://confluence.oci.oraclecorp.com/"
        self.conf_java_page_id = 3683202948
        self.conf = Confluence(
            url=self.conf_site,
            token=self.conf_token
        )
        self.repository_name = str(sys.argv[1]) if str(sys.argv[1]).endswith('/') else str(sys.argv[1]) + "/"
        self.repository_snapshot_name = str(sys.argv[2]) if str(sys.argv[2]).endswith('/') else str(sys.argv[2]) + "/"
        self.download_from_normal_and_snapshot_repo = True if self.repository_name != self.repository_snapshot_name else False
        pass

    def patch_conf_page(self, project_name, code_source, tag_name, report_link, build_id, build_commands):
        page = self.conf.get_page_by_id(page_id=self.conf_java_page_id, expand='body.storage')

        contents = page["body"]["storage"]["value"]

        soup = BeautifulSoup(str(contents), 'html.parser')
        validations_java_table_body = soup.find("tbody", {'class': 'validations_java_table_body'})

        last_child = None

        for elem in validations_java_table_body.find_all('tr'):
            if elem.nextSibling == None:
                last_child = elem
                break

        new_tr = soup.new_tag('tr')

        new_td1 = soup.new_tag('td')
        new_td1.append(project_name)

        new_td2 = soup.new_tag('td')
        new_td2.append(code_source)

        new_td3 = soup.new_tag('td')
        new_td3.append(tag_name)

        new_td4 = soup.new_tag('td')
        new_td4.append(build_id)


        new_td5 = soup.new_tag('td')
        anchor_tag = soup.new_tag('a', href=report_link, target='_blank')
        anchor_tag.append("main_report.html")
        new_td5.append(anchor_tag)

        new_td6 = soup.new_tag('td')
        new_td6.append("")

        new_td7 = soup.new_tag('td')
        new_td7.append("")

        new_td8 = soup.new_tag('td')
        if self.download_from_normal_and_snapshot_repo:
            new_td8.append(self.repository_name + "::" + self.repository_snapshot_name)
        else:
            new_td8.append(self.repository_name)

        new_td9 = soup.new_tag('td')
        new_td9.append(build_commands)

        new_tr.append(new_td1)
        new_tr.append(new_td2)
        new_tr.append(new_td3)
        new_tr.append(new_td4)
        new_tr.append(new_td5)
        new_tr.append(new_td6)
        new_tr.append(new_td7)
        new_tr.append(new_td8)
        new_tr.append(new_td9)

        validations_java_table_body.insert(len(validations_java_table_body.find_all('tr')), new_tr)

        self.conf.update_page(page_id=self.conf_java_page_id,body=str(soup), title="Validations_java")


class ObjectStorageHandler():
    def __init__(self) -> None:
        try:
            self.reports_dir = "reports_" + strftime("%Y%m%d%H%M%S", gmtime())
            os.makedirs(
                name=self.reports_dir,
                mode=777,
                exist_ok=True
            )
            self.key_content = None
            if os.getenv("OSS_PRIVATE_KEY_CONTENT") != None:
                self.key_content = base64.b64decode(os.getenv("OSS_PRIVATE_KEY_CONTENT"))
            if self.key_content == None:
                print ("Error: couldn't find the private key of object storage")
                sys.exit(1)
            self.conf = {
                "user":"ocid1.user.oc1..aaaaaaaaa5tvbgp5zuowekhh2hno7sdvg5zrpu7rlh7rvv7ajukdre3tye2q",
                "fingerprint":"fe:b0:41:f0:1f:b8:68:81:8e:fb:b2:9a:db:a9:88:7a",
                "tenancy":"ocid1.tenancy.oc1..aaaaaaaaggpkyphk4yxlv4h5ydns5x3jn3cxkgursuk36o5otsgouaq5axqq",
                "region":"eu-amsterdam-1",
                "namespace":"axhv41kty20f",
                "bucketname":"bucket-in-root",
                "key_content": self.key_content
            }
            self.base_url = "https://objectstorage.eu-amsterdam-1.oraclecloud.com/n/axhv41kty20f/b/bucket-in-root/o/reports"
            ##### connect to bucket
            self.object_storage_client = oci.object_storage.ObjectStorageClient(self.conf)
            print ("test the configuration...")
            oci.config.validate_config(self.conf)
            print("-- configuration passed --")
            self.namespace = self.conf["namespace"]
            self.bucketname = self.conf["bucketname"]
            return
        except oci.exceptions.ServiceError as serviceError:
            if serviceError.status >= 500:
                print("Error: internal server error on the oci object storage client")
                sys.exit(1)
            print ("non-2xx HTTP status")
            print (serviceError.message)
        except Exception as e:
            print ("default error ", e)
        sys.exit(1)

    def move_to_reports_dir(self):
        shutil.move(
            src="main_report.html",
            dst=self.reports_dir
        )
        if os.path.isdir('pkgdiff_reports'):
            shutil.move(
                src="pkgdiff_reports/",
                dst=self.reports_dir
            )
        return

    def get_base_url(self):
        return

    def patch_html_file_anchor_href(self):
            for root, dirs, files in os.walk(self.reports_dir):
                for filename in files:
                    if '.html' in filename:
                        with open(os.path.join(root, filename), 'rb') as file:
                            raw_data = file.read()
                            soup = BeautifulSoup(raw_data, 'html.parser', from_encoding='utf-8')
                            # Extract the text content from the soup
                            readContent = str(soup)
                            root_path = root.replace('\\','/') if platform.system() == "Windows" else root
                            newContent = re.sub(
                                pattern=r"href=(\"|\')((?!#|http))",
                                repl=r"href=\1{}/{}/".format(self.base_url,root_path),
                                string=readContent
                            )

                            with open(os.path.join(root, filename), 'w') as writeContent:
                                writeContent.write(newContent)
                    else:
                        print ("diff filename = ", filename, os.path.join(root, filename))

    def upload_to_oss(self):
        try:
            for root, dirs, files in os.walk(self.reports_dir):
                for filename in files:
                    root_path = root.replace('\\','/') if platform.system() == "Windows" else root
                    print ("upload file ", "reports/" + root_path + "/" + filename)
                    self.object_storage_client.put_object(
                        namespace_name=self.namespace,
                        bucket_name=self.bucketname,
                        object_name="reports/" + root_path + "/" + filename,
                        put_object_body=open(os.path.join(root, filename), 'rb')
                    )
            return True
        except oci.exceptions.ServiceError as serviceError:
            if serviceError.status >= 500:
                print ("Error: oss internal server error")
                return False
            print ("non-2xx HTTP status")
            print (serviceError.message)
        except Exception as e:
            print ("default error ", e)
        return False


    def upload(self, general_info):
        self.move_to_reports_dir()
        # Patch the href on anchor tag in every html file to containe the new url + path to file
        self.patch_html_file_anchor_href()
        resp = self.upload_to_oss()
        if resp:
            # start the work for confluence page
            confluenceHandler = ConfluenceHandler()
            confluenceHandler.patch_conf_page(project_name=general_info["project_name"],code_source=general_info["source_code"],tag_name=general_info["tag_name"],report_link=self.base_url + "/" + self.reports_dir + "/main_report.html",build_id=general_info["build_id"], build_commands=general_info["build_commands"])
            return
        else:
            # clear the bucket /reports/self.reports_dir/*
            return
        return

class HandleSuffix():
    def __init__(self) -> None:
        self.common = []
        self.left_only = []
        self.right_only = []
        self.mapOurFiles = {}
        self.versionsTuple = None
        pass

    def omitOracleSuffix(self,ourFileName: str):
        """
        we should fix at lease our qualifier that we will add to the version while building them to something like -bfsoracle-00001
        so we can avert a conflict if a team use the -oracle-0000x as a qualifier to there build
        we should mark the artifacts build by our service unique.
        """

        return "".join(re.split(
            pattern=r"-oracle-\d+",
            string=ourFileName
        ))

    def compareFoldersWithOracleSuffix(self,ourFolder, mavenFolder, artifact_id, version):
        # should return cmpDir object {common, left_only#just in maven folder, right_only#just in our folder}
        mavenFiles = [mvnFile for mvnFile in os.listdir(mavenFolder)]
        ourFiles = [self.omitOracleSuffix(ourFile) for ourFile in os.listdir(ourFolder)]
        for ourFile in os.listdir(ourFolder):
            self.mapOurFiles[self.omitOracleSuffix(ourFile)] = ourFile

        common_files = set(mavenFiles) & set(ourFiles)

        onlyInMaven_files = set(mavenFiles) - set(ourFiles)

        onlyInOurBuild_files = set(ourFiles) - set(mavenFiles)
        self.common = list(common_files)
        self.left_only = list(onlyInMaven_files)
        self.right_only = [self.mapOurFiles[our] for our in list(onlyInOurBuild_files)]
        self.versionsTuple = (version, self.omitOracleSuffix(version))

class DownloadFromMirrorMavenCentral():
    def __init__(self) -> None:
        self.downloadDir = "bfs_download_central_artifacts"
        self.ourBuildDownloadDir = "bfs_download_our_artifacts"
        self.artifactory_base_url    = f"https://artifacthub-phx.oci.oraclecorp.com/libs-release/"

        repository_name = str(sys.argv[1]) if str(sys.argv[1]).endswith('/') else str(sys.argv[1]) + "/"
        repository_snapshot_name = str(sys.argv[2]) if str(sys.argv[2]).endswith('/') else str(sys.argv[2]) + "/"

        self.download_from_normal_and_snapshot_repo = True if repository_name != repository_snapshot_name else False
        self.ourArtifactory_base_url = f"https://artifactory.oci.oraclecorp.com/" + repository_name
        self.ourArtifactory_snapshot_base_url = None
        if self.download_from_normal_and_snapshot_repo:
            self.ourArtifactory_snapshot_base_url = f"https://artifactory.oci.oraclecorp.com/" + repository_snapshot_name
        self.token = os.getenv("ARTIFACTORY_TOKEN")
        if self.token == None:
            print ("Error: couldn't find the artifactory token")
            # sys.exit(1)
        # remove this connect phase no need for it
        connect = ArtifactoryPath(
            self.artifactory_base_url,
            token=self.token
        )
        self.pkgdiffUrl = 'https://artifacthub-phx.oci.oraclecorp.com/artifactory/oscs-oci-tpa-stage-local/com/oracle/oscs/Jar-Comparison/pkgdiff.tar.gz'
        target_path = 'pkgdiff.tar.gz'
        folderName = "bfs_compare"


        response = requests.get(self.pkgdiffUrl, stream=True)
        if response.status_code == 200:
            with open(target_path, 'wb') as f:
                f.write(response.raw.read())
                print("ok")
            shutil.unpack_archive(target_path, folderName)
            print("file has been extracted")
        else:
            print ("Error: can't download the pkgdiff tool from ", self.pkgdiffUrl)
            sys.exit(1)
        pass

    def getAllLibsReleaseDownloadPath(self,url: str):
        page_content = requests.get(url, stream=True)
        if page_content.status_code != 200:
            print ("Error: could find the url ", url)
            return []

        soup = BeautifulSoup(str(page_content.text), 'html.parser')
        anchorLink_list = soup.find_all('a')
        listArtifactPath = []
        for a in anchorLink_list:
            if any(t in a.text for t in ['../', '.asc', '.sha512', '.sha256', '.sha1', '.md5']):
                continue
            if url + a.text not in listArtifactPath:
                listArtifactPath.append(url + a.text)
        print (listArtifactPath)
        return listArtifactPath

    def downloadFromMirrorMavenCentral(self, destDir:str,group_id:str, artifact_id:str, version:str):
        try:
            mavenVersion = version
            if "-oracle-" in version:
                mavenVersion = version[:version.index("-oracle-")]

            path = self.getAllLibsReleaseDownloadPath(
                url=self.artifactory_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + mavenVersion + "/"
            )
            if len(path) == 0:
                return "failed"

            outDir = self.downloadDir + destDir + "/"

            os.makedirs(
                name=outDir,
                mode=777,
                exist_ok=True
            )
            for p in path:
                response = requests.get(str(p), stream=True)
                if response.status_code != 200:
                    return "failed"
                with open(outDir + str(p).split('/')[-1], 'wb+') as f:
                    f.write(response.raw.read())

            ourPath = ArtifactoryPath(
                self.ourArtifactory_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + version + "/",
            )
            ourOutDir = self.ourBuildDownloadDir + destDir + "/"
            os.makedirs(
                name=ourOutDir,
                mode=777,
                exist_ok=True
            )
            downloadFailCount = 0
            try:
                for op in ourPath:
                    response = requests.get(str(op), stream=True)
                    if response.status_code != 200:
                        return "failed"
                    with open(ourOutDir + str(op).split('/')[-1], 'wb+') as f:
                        f.write(response.raw.read())
            except Exception as e:
                print ("Error: could find the repository ", self.ourArtifactory_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + version + "/")
                downloadFailCount += 1

            if self.ourArtifactory_snapshot_base_url != None:
                ourSnapshotPath = ArtifactoryPath(
                    self.ourArtifactory_snapshot_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + version + "/",
                )
                try:
                    for op in ourSnapshotPath:
                        response = requests.get(str(op), stream=True)
                        if response.status_code != 200:
                            return "failed"
                        with open(ourOutDir + str(op).split('/')[-1], 'wb+') as f:
                            f.write(response.raw.read())
                except Exception as e:
                    print ("Error: could find the repository ", self.ourArtifactory_snapshot_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + version + "/")
                    downloadFailCount += 1

                if downloadFailCount == 2:
                    print ("Error: could donwload form both repo = ", self.ourArtifactory_base_url, " and snapshot repo = ",self.ourArtifactory_snapshot_base_url)
                    return "failed"
            elif downloadFailCount == 1:
                print ("Error: couldn't find the repository ", self.ourArtifactory_base_url)
                return "failed"

            return "success"
        except ArtifactoryException as ae:
            print ("failed to download ", self.artifactory_base_url + group_id.replace(".","/") + "/" + artifact_id + "/" + version)
            return "failed"

    def compareWithMirrorMavenCentral(self, destDir:str, artifact_id:str, version:str):
        return self.compareFolders(
            ourFolder= self.ourBuildDownloadDir + destDir,
            mavenFolder=self.downloadDir + destDir,
            artifact_id=artifact_id,
            version=version
        )

    def compareFolders(self, ourFolder, mavenFolder,artifact_id, version):
        cmpDir = None
        oracleSuffix = False
        if "-oracle-" in version:
            oracleSuffix = True
            cmpDir = HandleSuffix()
            cmpDir.compareFoldersWithOracleSuffix(
                ourFolder=ourFolder,
                mavenFolder=mavenFolder,
                artifact_id=artifact_id,
                version=version
            )
        else:
            cmpDir = filecmp.dircmp(
                a=mavenFolder,
                b=ourFolder,
            )

        common_info = []
        for comn in cmpDir.common:
            ourFile = comn
            versionsTuple = (version, version)
            if oracleSuffix:
                # -vnum1 and -vnum2
                versionsTuple = cmpDir.versionsTuple
                ourFile = cmpDir.mapOurFiles[comn]
            basePathName:str = "pkgdiff_reports/" + artifact_id + "/" + ourFile.replace('.', '_') + "_to_" + comn.replace('.', '_')
            pathName:str = basePathName + "/changes_report.html"
            if any(ext in comn for ext in ['.jar', '.war','.ear','.zip','.tar','.tar.gz']):
                p = subprocess.run(["./bfs_compare/pkgdiff/pkgdiff.pl" ,"-details", mavenFolder + "/" + comn, ourFolder +"/"+ ourFile,  "-report-path", pathName, "-vnum1", versionsTuple[0], "-vnum2", versionsTuple[1] ], shell=False)
                common_info.append({
                    "main_report_path": pathName,
                    "artifact_name": comn,
                    "ourArtifact_name": ourFile if oracleSuffix else comn
                })
            else:
                if any(ext in comn for ext in ['pom', 'module','xml','.json']):
                    os.makedirs(
                        name=basePathName,
                        mode=777,
                        exist_ok=True
                    )
                    cmd:str = "sh" + " " + "bfs_compare/pkgdiff/modules/Internals/Tools/rfcdiff-1.41-CUSTOM.sh" + " " + "--width" + " " + "80" + " " + "--stdout" + " " + mavenFolder + "/" + comn + " " + ourFolder +"/"+ ourFile + " > " + basePathName + "/changes_report.html"

                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,shell=True)
                    output = process.communicate()[0]

                    common_info.append({
                        "main_report_path": basePathName + "/changes_report.html",
                        "artifact_name": comn,
                        "ourArtifact_name": ourFile if oracleSuffix else comn
                    })

        return {
            "onlyInMaven": list(filter(lambda x: all(i not in x for i in ['.asc','.sha512','.sha256','.md5','.sha1']), cmpDir.left_only)),
            "onlyInOurBuild": list(filter(lambda x: all(i not in x for i in ['.asc','.sha512','.sha256','.md5','.sha1']) and artifact_id in x ,cmpDir.right_only)),
            "common_info": common_info
        }


listDownloadFromCentral = []

#utils functions
def print_nested_folder(directory:dict, d: str):
    for filename in directory.keys():
        if not isinstance(directory[filename], dict) or filename in ["project-general-info", "groupId", "artifactId", "version"]:
            continue
        else:
            p = d + "/" + filename
            listDownloadFromCentral.append({
                "path" : p,
                "gav" : {
                    "groupId": directory[filename]["groupId"],
                    "artifactId": directory[filename]["artifactId"],
                    "version": directory[filename]["version"]
                },
                "downloadStatus": ""
            })
            print_nested_folder(directory[filename], p)


def generate_global_report(general_info: dict,compare_list: list):
    doc, tag, text = Doc().tagtext()

    doc.asis('<!DOCTYPE html>')
    with tag('html'):
        with tag('head'):
            with tag('title'):
                text('main_report')
        with tag('body'):
            with tag('h1'):
                text('General information:')
        for k, v in general_info.items():
            with tag('p'):
                text(k + " = " + v)

        with tag('h1'):
            text('Comparison:')
        for module_info in compare_list:
            with tag('h3'):
                text("module = " + module_info["module"])
            with tag('div', style='border: solid black 1px;'):
              with tag('table', style='border-collapse: collapse;',width='900px'):
                  with tag('tbody'):
                      with tag('tr', style="background-color: bisque;"):
                          with tag('td', style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                              text('GroupId')
                          with tag('td', style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                              text('ArtifactId')
                          with tag('td', style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                              text('Version')
                      with tag('tr'):
                          with tag('td', style="border: 1px solid black; padding: 5px;"):
                              text(module_info["groupId"])
                          with tag('td', style="border: 1px solid black; padding: 5px;"):
                              text(module_info["artifactId"])
                          with tag('td', style="border: 1px solid black; padding: 5px;"):
                              text(module_info["version"])
              if "compare_info" not in module_info:
                  with tag('p'):
                    text(module_info["error"])
                  continue
              onlyInMaven:list = module_info["compare_info"]["onlyInMaven"]
              onlyInOurBuild:list = module_info["compare_info"]["onlyInOurBuild"]
              common_info:list = module_info["compare_info"]["common_info"]

              with tag('p', style="font-weight: bold;"):
                text('-Only in Maven Central Mirror (libs-release)--')
                with tag('div', style="padding: 10px;border: solid black 1px;background-color:rgb(243, 84, 84);"):
                  for mvn in onlyInMaven:
                      with tag('p'):
                          text(mvn)

              with tag('p', style="font-weight: bold;"):
                text('-Only in our Build --')
                with tag('div',style="padding: 10px;border: solid black 1px;background-color:rgb(228, 159, 55);"):
                  for ourbuild in onlyInOurBuild:
                      with tag('p'):
                          text(ourbuild)
              with tag('p', style="font-weight: bold;"):
                 text('-Common Files --')
              with tag('table',width = "900px", style="border-collapse: collapse;"):
                with tag('tbody'):
                  with tag('tr', style="background-color: bisque;"):
                    with tag('td',style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                      text("Maven Central Mirror Artifact Name")
                    with tag('td',style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                      text("Our Artifact Name")
                    with tag('td',style="font-weight: bold;border: 1px solid black; padding: 5px;"):
                      text("Report Path")

                  for cmn_info in common_info:
                    with tag('tr'):
                      with tag('td',style="border: 1px solid black; padding: 5px;"):
                        text(cmn_info["artifact_name"])
                      with tag('td',style="border: 1px solid black; padding: 5px;"):
                        text(cmn_info["ourArtifact_name"])
                      with tag('td',style="border: 1px solid black; padding: 5px;"):
                        with tag('a', href=cmn_info["main_report_path"]):
                          text("link")


    result = indent(doc.getvalue())
    with open('main_report.html', 'w') as file:
        file.writelines(result)
    return

ourPublishArtifactoryUrl = "https://artifactory.oci.oraclecorp.com/bt3po-source-build-release-maven-local/"

def main():
    parsedToml = ParseToml(pathTestToml)
    print (parsedToml.tomlParsed)
    tomlObject : dict = parsedToml.tomlParsed
    # extract general information
    build_type : str    = tomlObject['project-general-info']["build-type"]
    jdk_version : str   = tomlObject['project-general-info']["jdk-version"]
    project_name : str  = tomlObject['project-general-info']["project-name"]
    source_code : str   = tomlObject['project-general-info']["source-code"]
    tag_name : str      = tomlObject['project-general-info']["tag-name"]
    build_id : str      = tomlObject['project-general-info']["build-id"]
    build_commands : str      = tomlObject['project-general-info']["build-commands"]
    # get the suffix from the toml file
    version_suffix: str     = tomlObject["project-general-info"]["version-suffix"]
    general_info = {
        "project_name": project_name,
        "build_type": build_type,
        "jdk_version": jdk_version,
        "source_code": source_code,
        "tag_name": tag_name,
        "build_id": build_id,
        "build_commands": build_commands,
    }
    # collect the comparison information
    compare_list = []
    print (build_type)

    print_nested_folder(tomlObject, "")

    dmc = DownloadFromMirrorMavenCentral()
    for repo in listDownloadFromCentral:
        groupId = repo["gav"]["groupId"]
        artifactId = repo["gav"]["artifactId"]
        # add suffix
        version = repo["gav"]["version"] + version_suffix
        print(repo["path"], groupId, artifactId, version)

        downloadStatus = dmc.downloadFromMirrorMavenCentral(repo["path"], groupId, artifactId, version)
        repo["downloadStatus"] = downloadStatus

        if downloadStatus == "success":
            compare_info = dmc.compareWithMirrorMavenCentral(repo["path"], artifactId, version)

            compare_list.append(
                {
                    "module": repo["path"],
                    "groupId": groupId,
                    "artifactId": artifactId,
                    "version": version,
                    "compare_info": compare_info
                }
            )

        else:
            compare_list.append(
                {
                    "module": repo["path"],
                    "groupId": groupId,
                    "artifactId": artifactId,
                    "version": version,
                    "error": "failed to download this gav"
                }
            )
    print (general_info)
    print (compare_list)
    generate_global_report(
        general_info=general_info,
        compare_list=compare_list
    )

    objectStorageHandler =  ObjectStorageHandler()

    objectStorageHandler.upload(general_info)
    return

if __name__ == "__main__":
    main()