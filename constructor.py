import yaml
import re


"""
autmates filling out a coreos cloudconfig file from a 'master'
cloud config file
"""

class EnvDict(dict):
    @staticmethod
    def chkvar(var):
        if var[0].isalpha() is not True:
            raise ValueError("have to begin w/ letter")
    @staticmethod
    def replacementtoken(var):
        return '${'+var.upper()+'}'
    @staticmethod
    def unreplacementtoken(var):
        var=var.strip()
        var=var.replace('$','')
        var=var.replace('{','')
        var=var.replace('}','')
        EnvDict.chkvar(var)
        var=var.upper()
        return var
    
    def __setitem__(self, k, v):
        k=EnvDict.unreplacementtoken(k)
        if v is None: v=EnvDict.replacementtoken(k)
        v=str(v)
        return super(EnvDict,self).__setitem__(k,v)
    def __getitem__(self, k):
        k=EnvDict.unreplacementtoken(k)
        return super(EnvDict,self).__getitem__((k))
        




#here i'm trying to id parts of the yml file that are in lists
#each list item has an identifying item 'header' as follows
coreos_sectionIDs={'write_files': 'path'
                   ,'users':'name'
                   ,'coreos.units':'name'}

def getFromDict(dataDict, mapList):
    """gets a value from a nested dictionary"""
    return reduce(lambda d, k: d[k], mapList, dataDict)
def getFromYml(*args):
    args=list(args)
    args[1]=args[1].split('.')
    return getFromDict(*args)
def _dot2brackets(dotstr):
    #hack enabler
    alibrary=dotstr.split('.')
    brackets=''
    for k in alibrary:
        if k=='': continue
        brackets+="['"+k+"']"
    return brackets

        
def get_ymlitem(section,ID, ymlo,sectionIDs=coreos_sectionIDs):
    """given a yml obj, find the list item"""

    if section not in sectionIDs:
        raise ValueError('section not identified')
    #have to loop through a list
    for anitem in getFromYml(ymlo,section):#list
        if anitem[sectionIDs[section]]==ID:
            return anitem

#catches $V ${V} $VAR ${VAR} $VAR_3 ${VAR3_4}
var_regex=ur'(\${*[A-Z]+[A-Z_0-9]+}*|\${*[A-Z]}*)'
        
def get_vars(astr):
    """gets $VAR and ${VAR}. Only considering caps"""
    astr=repl_myassignments(astr)
    p= re.compile(var_regex, re.VERBOSE)
    vars = re.findall(p, astr)
    vars = [EnvDict.unreplacementtoken(avar) for avar in vars]
    return set(vars)

def repl_myassignments(astr):
    """if somewhere i put VAR== then make it VAR=$VAR"""
    p = re.compile(ur'[A-Z_]+[A-Z_0-9]?==', re.VERBOSE)
    #vars = re.findall(p, astr)
    def repl(match):
        s=match.start()
        e=match.end()
        var=match.string[s:e-2]
        return var+'='+'$'+var
    return p.sub(repl,astr)


def subs(astr,subs_dict):
    """nice behavior: get the keys from the str with get_vars
    then envdict.fromkeys then give it to this func"""
    sd=EnvDict()
    sd.update(subs_dict); 
    subs_dict=sd
    astr=repl_myassignments(astr)
    p = re.compile(var_regex, re.VERBOSE)

    def repl(match):
        s=match.start()
        e=match.end()
        var=EnvDict.unreplacementtoken(match.string[s:e])
        try:
            return subs_dict[var]
        except:
            subs_dict[var]=None
            return subs_dict[var]
        
    #replacements within dictionary. nested replacements
    # VAR=1
    # VAR1=$VAR
    # VAR2=$VAR1
    # VAR3=$VAR2
    # ANOTHERVAR=${UNDEFINED}
    # will loop until VAR, VAR1, VAR2, VAR3 all = 1
    def nv(): return len(get_vars(''.join(subs_dict.values())))
    while True:
        pnv=nv()
        subs_dict2=subs_dict.copy()
        for avar,aval in subs_dict2.iteritems():
            subs_dict2[avar]=p.sub(repl,aval)
        subs_dict.update(subs_dict2)
        cnv=nv();
        #loop until can't make any more replacements
        if cnv==pnv: break
    #print subs_dict#check
    
    #replacements in yaml
    return p.sub(repl,astr)


def read_envfile(envfile):
    """makes a dict out of entries in an env file"""
    envs={}
    for aline in envfile:
        if aline[0]=='#': continue
        if '=' not in aline: continue
        var,val=aline.split('=')
        var=var.strip()
        val=val.strip()
        envs[var]=val
    return envs



def assemble_cloudconfig( library_file,  appyml_file, envfiles=[]  ):
    """
    library_file: the 'master'/'template' cloud config file
    appyml_file: a, perhaps smaller, filled out cloud config file
    envfiles: list of environment variables. # comment allowed
    """
    
    #make one env dict. later env file entries are overridden
    envs={}
    ymllibo=yaml.load(library_file)
    for aenvf in envfiles:
        envsf=read_envfile(aenvf)
        for k,v in envsf.iteritems(): envs[k]=v
    
    #put together
    ymlo=yaml.load(appyml_file)
    for asec in coreos_sectionIDs:
        try: appitems=getFromYml(ymlo,asec)
        #eg [{'name':docker.service'}...{'name':etcd.service} ]
        except: continue #this section doesn not exist
        secid=coreos_sectionIDs[asec] #'name'
        items=[]
        for anitem in appitems:#skeleton items
            #get the item from 'library/template/master'
            try:
                libraryitem=get_ymlitem(asec,anitem[secid],ymllibo)
           #               = {'name':etcd.service,'contents': ...}
            except:
                #section does not exist in master file.
                libraryitem={}
            if libraryitem==None:
                #section.item does not exist in master file
                libraryitem={}
            #allow for the skeleton to overwrite the master
            libraryitem.update(anitem)
            #HACKKK
            acc=_dot2brackets(asec)
            items.append(libraryitem)
        #..and put it in the 'app'
        exec('ymlo'+acc+'=items')

    return '#cloud-config\n\n'+\
        subs(yaml.dump(ymlo,default_flow_style=False),envs)

def notassigned(*args,**kwargs):
    """
    takes assemble_cloudconfig args and tells you if you are
    missing values for env vars
    """
    ymlstr=assemble_cloudconfig(*args,**kwargs)
    return get_vars(repl_myassignments((ymlstr)))

def strnotassigned(*args,**kwargs):
    """just for a printout of notassigneed"""
    envsset=notassigned(*args,**kwargs)
    envsstr=''
    for anenv in envsset: envsstr+=anenv+'\n'
    return envsstr
    

def summary(yml_file):
    """convenience function that shows you just 'headers'
    of a cloud-config file.
    and its env vars """

    envsset=get_vars(repl_myassignments((yml_file.read())))
    envsstr=''
    for anenv in envsset: envsstr+=anenv+'\n'

    #put together
    yml_file.seek(0)
    ymlo=yaml.load(yml_file);
    yml_file.seek(0)
    ymlol=yaml.load(yml_file)
    for asec in coreos_sectionIDs:
        try: appitems=getFromYml(ymlo,asec)
        #eg [{'name':docker.service'}...{'name':etcd.service} ]
        except: continue #this section doesn not exist
        secid=coreos_sectionIDs[asec] #'name'
        items=[]
        for anitem in appitems:
            #get the item from 'library/template'
            libraryitem=get_ymlitem(asec,anitem[secid],ymlol)
            #          = {'name':etcd.service,contents: ...}
            #HACKKK
            acc=_dot2brackets(asec)
            items.append({secid:libraryitem[secid]})
            #items.append(libraRyitem[Secid])#this looks nicer...
            #and less verbose but let's make it look more like
            #a valid cloudconfig file to make it easy to cpy/paste
        #..and put it in the 'app'
        exec('ymlo'+acc+'=items')

    return '#cloud-config\n'+\
        (yaml.dump(ymlo,default_flow_style=False))\
        ,envsstr


if __name__=='__main__':
    
    import sys
    import os
    
    thisfn=os.path.basename(__file__)
    usage=\
"""
Populate a 'skeleton' CoreOS cloud-config file from a 'master' (populated) file.
Optionally use a series of environment files to subsitute environment variables
(or any replacement token in the file).
    
To generate:
> python %s master.yml skeleton.yml [envfile1 envfile2 ... ]

Helpers:
- skeleton
  Make a 'skeleton' from the contents of your 'master'/'template'. You can then
  just remove entries from the output if you want.
  > python %s skeleton  master.yml
- variables
  Get a list of environment variables (or any replacement token) from a
  cloud-config file.
  > python %s variables master.yml
- unassigned
  Find variables not substituted for by adding 'unassigned' to the arguments
  used to generate a cloud-init file.
  python %s unassigned master.yml skeleton.yml [envfile1 envfile2 ... ] 
""" % (thisfn,thisfn,thisfn,thisfn)

    def argsfor_assemble_cloudconfig( *args  ): #return args, and kwargs
        #from  a 'flat' args list, adapt for use
        """adapting it to use from the cmd line"""
        kwargs={}
        kwargs.setdefault('envfiles',[])
        try:
            kwargs['envfiles']=args[2:]
            args=args[0:2]
        except:pass
        return args,kwargs
        #return assemble_cloudconfig( *args , **kwargs)


    encoding='utf8' #changes to this does not work on my windows machine
    #check on linux.
    #import codecs
    #sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    args=sys.argv
    if len(args)==1: #just the file itself
        print(usage)
        sys.exit()

    def files(fns): return [open(af,'r') for af in fns]
    subcmd=args[1]
    if subcmd=='skeleton':
        sys.stdout.write(unicode(summary(*files(args[2:]))[0])\
              .encode(encoding))
    elif subcmd=='variables':
        sys.stdout.write(unicode(summary(*files(args[2:]))[1])\
              .encode(encoding))
    elif subcmd=='unassigned':
        sargs=argsfor_assemble_cloudconfig( *files(args[2:])  )
        sys.stdout.write(unicode(strnotassigned(*sargs[0],**sargs[1]))\
              .encode(encoding))
    else:#the 'main' cmd
        sargs=argsfor_assemble_cloudconfig( *files(args[1:])  )
        sys.stdout.write(unicode(assemble_cloudconfig(*sargs[0],**sargs[1]))\
              .encode(encoding))
        
    sys.exit()


    

    
