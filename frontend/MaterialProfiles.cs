using System;
using System.Collections.Generic;
using System.IO;
using System.Xml;

namespace Aurora.Frontend
{
    // Named presets contain a complete selection, never a reference consulted
    // by a queued print. Loading a preset only edits the current dialog.
    public sealed class MaterialProfiles
    {
        readonly string path;
        readonly PreferenceData data;
        byte[] loaded;
        readonly SortedDictionary<string,Dictionary<string,string>> profiles =
            new SortedDictionary<string,Dictionary<string,string>>(StringComparer.OrdinalIgnoreCase);
        public MaterialProfiles(string path,PreferenceData data)
        {
            this.path=Path.GetFullPath(path);this.data=data;
            if(!File.Exists(this.path)) return;
            if(new FileInfo(this.path).Length>256*1024) throw new InvalidDataException("Material profile file is too large.");
            loaded=File.ReadAllBytes(this.path);
            XmlDocument document=new XmlDocument {XmlResolver=null};
            using(XmlReader reader=XmlReader.Create(new MemoryStream(loaded),new XmlReaderSettings {
                DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=256*1024 })) document.Load(reader);
            XmlElement root=document.DocumentElement;
            if(root.Name!="AuroraMaterialProfiles" || root.GetAttribute("version")!="1")
                throw new InvalidDataException("Unsupported material profile file.");
            foreach(XmlNode node in root.ChildNodes)
            {
                XmlElement profile=node as XmlElement;
                if(profile==null) continue;
                if(profile.Name!="Material" || profiles.Count>=200) throw new InvalidDataException("Invalid material profiles.");
                string name=CheckName(profile.GetAttribute("name"));
                Dictionary<string,string> values=new Dictionary<string,string>();
                foreach(XmlNode item in profile.ChildNodes)
                {
                    XmlElement setting=item as XmlElement;
                    if(setting==null) continue;
                    if(setting.Name!="Setting") throw new InvalidDataException("Invalid material setting.");
                    values.Add(setting.GetAttribute("key"),setting.GetAttribute("value"));
                }
                data.Check(values);
                profiles.Add(name,values);
            }
        }
        public static string DefaultPath { get { return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AuroraJobServer","material-profiles.xml"); } }
        public static string CheckName(string name)
        {
            name=(name??"").Trim();
            if(name.Length==0 || name.Length>64 || name.IndexOfAny(new char[]{'\r','\n','\t'})>=0)
                throw new ArgumentException("Enter a material name of 1–64 characters.");
            return name;
        }
        public string[] Names { get { string[] names=new string[profiles.Count];profiles.Keys.CopyTo(names,0);return names; } }
        public bool Contains(string name) { return profiles.ContainsKey(CheckName(name)); }
        public Dictionary<string,string> Get(string name) { return new Dictionary<string,string>(profiles[CheckName(name)]); }
        public void Save(string name,Dictionary<string,string> selection)
        {
            name=CheckName(name);data.Check(selection);
            if(!profiles.ContainsKey(name) && profiles.Count>=200) throw new InvalidOperationException("Keep at most 200 materials.");
            Dictionary<string,string> previous=profiles.ContainsKey(name)?profiles[name]:null;
            profiles[name]=new Dictionary<string,string>(selection);
            try { Write(); }
            catch { if(previous==null) profiles.Remove(name);else profiles[name]=previous;throw; }
        }
        public void Delete(string name)
        {
            name=CheckName(name);Dictionary<string,string> previous=profiles[name];profiles.Remove(name);
            try { Write(); } catch { profiles[name]=previous;throw; }
        }
        void Write()
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            // Serialize other Properties windows and reject stale preset edits.
            using(FileStream profileLock=new FileStream(path+".lock",FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
            {
            byte[] current=File.Exists(path)?File.ReadAllBytes(path):null;
            if(!Equal(loaded,current)) throw new IOException("Materials changed in another Properties window. Reopen Properties before saving.");
            string temporary=path+"."+Guid.NewGuid().ToString("N")+".tmp";
            try
            {
                using(FileStream file=new FileStream(temporary,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                {
                    using(XmlWriter writer=XmlWriter.Create(file,new XmlWriterSettings {Indent=true,CloseOutput=false}))
                    {
                        writer.WriteStartElement("AuroraMaterialProfiles");writer.WriteAttributeString("version","1");
                        foreach(var profile in profiles)
                        {
                            writer.WriteStartElement("Material");writer.WriteAttributeString("name",profile.Key);
                            foreach(string key in PreferenceData.Keys)
                            { writer.WriteStartElement("Setting");writer.WriteAttributeString("key",key);writer.WriteAttributeString("value",profile.Value[key]);writer.WriteEndElement(); }
                            writer.WriteEndElement();
                        }
                        writer.WriteEndElement();
                    }
                    file.Flush(true);
                }
                if(File.Exists(path)) File.Replace(temporary,path,null);else File.Move(temporary,path);
                loaded=File.ReadAllBytes(path);
            }
            finally { if(File.Exists(temporary)) File.Delete(temporary); }
            }
        }
        static bool Equal(byte[] left,byte[] right)
        {
            if(left==null || right==null) return left==right;
            if(left.Length!=right.Length) return false;
            for(int i=0;i<left.Length;i++) if(left[i]!=right[i]) return false;
            return true;
        }
    }
}
