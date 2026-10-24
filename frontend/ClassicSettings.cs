using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Xml;
using System.Xml.Serialization;

namespace Aurora.Frontend
{
    public enum ClassicOutput { RasterOnly, VectorOnly, RasterAndVector }
    public enum ClassicFocus { None, Manual, Thickness, Autofocus }
    public enum ClassicBitmap { ClipArt, Photo, Custom }
    public enum ClassicDither { Ordered4, Ordered8, FloydSteinberg, Jarvis, Stucki }
    public enum ClassicOrientation { Normal, Left90, Right90, UpsideDown }

    public sealed class ClassicColor
    {
        public string Name;
        public int R,G,B;
        public bool Enabled=true;
        public decimal PowerPercent,SpeedIps;
        public int Ppi=1000;
    }

    [XmlRoot("AuroraPreferences")]
    public sealed class ClassicSettings
    {
        // Version 2 stores TravelSpeed in ips. Version 1 is retained only for
        // reading old snapshots; its sole supported native value was 100.
        public int Version=2;
        public ClassicOutput Output=ClassicOutput.RasterAndVector;
        public decimal RasterPower=45,RasterSpeed=30,VectorPower=15,VectorSpeed=1;
        public int VectorPpi=1000,Resolution=167;
        public bool UseColors,SortColors=true,PauseColors,InvertRaster,BottomUp;
        public ClassicFocus Focus=ClassicFocus.None;
        public decimal ThicknessInches=0.020M;
        public bool Autostart,BeamConstantlyOn=true;
        public decimal PlateWidthInches=30,PlateHeightInches=18,OffsetXInches,OffsetYInches;
        public bool Cylindrical,CenterHorizontal,CenterVertical;
        public decimal TravelSpeed=.100M;
        public ClassicBitmap BitmapMode=ClassicBitmap.Custom;
        public bool DitherBitmaps;
        public ClassicDither Dither=ClassicDither.FloydSteinberg;
        public bool ManualContrast;
        public int ContrastLow,ContrastHigh=255,ContrastColors=256;
        public ClassicOrientation Orientation=ClassicOrientation.Normal;
        public bool Mirror,RubberStamp;
        public string StampProfile="Factory Default 1";
        public string OutputDirectory="JobServer archive";
        public bool DefaultFilename=true,AppendDateTime;
        public string LaserModel="Aurora";
        public string ColorProfile="All_colors (screenshot reference)";
        public ClassicColor[] Colors=Palette();

        public static readonly int[] Resolutions={50,100,167,200,250,333,500,1000,1200};
        public static ClassicColor[] Palette()
        {
            string[] names={"Black","Red","Navy","Magenta","Maroon","Lime","Olive","Aqua","Gray","Blue","Purple","Silver","Green","Yellow","Teal","White"};
            int[] rgb={0x000000,0xff0000,0x000080,0xff00ff,0x800000,0x00ff00,0x808000,0x00ffff,0x808080,0x0000ff,0x800080,0xc0c0c0,0x008000,0xffff00,0x008080,0xffffff};
            int[] power={100,95,90,85,80,75,70,65,60,55,50,45,40,30,20,10};
            ClassicColor[] result=new ClassicColor[16];
            for(int i=0;i<16;i++) result[i]=new ClassicColor {Name=names[i],R=(rgb[i]>>16)&255,G=(rgb[i]>>8)&255,B=rgb[i]&255,PowerPercent=power[i],SpeedIps=100};
            return result;
        }

        static void Range(decimal value,decimal low,decimal high,string label)
        {if(value<low || value>high) throw new InvalidDataException(label+" is outside its input range.");}
        static void Precision(decimal value,int digits,string label)
        {if(Decimal.Round(value,digits)!=value) throw new InvalidDataException(label+" has too many decimal places.");}
        public void Validate()
        {
            if((Version!=1 && Version!=2) || !Enum.IsDefined(typeof(ClassicOutput),Output) || !Enum.IsDefined(typeof(ClassicFocus),Focus) ||
                !Enum.IsDefined(typeof(ClassicBitmap),BitmapMode) || !Enum.IsDefined(typeof(ClassicDither),Dither) ||
                !Enum.IsDefined(typeof(ClassicOrientation),Orientation)) throw new InvalidDataException("Unknown settings version or mode.");
            Range(RasterPower,0,100,"Raster power");Range(VectorPower,0,100,"Vector power");
            Range(RasterSpeed,.001M,150,"Raster speed");Range(VectorSpeed,.001M,15,"Vector speed");
            Precision(RasterPower,2,"Raster power");Precision(VectorPower,2,"Vector power");Precision(RasterSpeed,3,"Raster speed");Precision(VectorSpeed,3,"Vector speed");Precision(TravelSpeed,3,"Travel speed");
            Range(VectorPpi,5,1000,"Vector PPI");Range(TravelSpeed,.001M,250,"Travel speed");
            if(Array.IndexOf(Resolutions,Resolution)<0) throw new InvalidDataException("Unknown original resolution.");
            Range(PlateWidthInches,.001M,30,"Plate width");Range(PlateHeightInches,.001M,18,"Plate height");
            Range(OffsetXInches,-30,30,"Horizontal offset");Range(OffsetYInches,-18,18,"Vertical offset");
            Range(ThicknessInches,0,18,"Material thickness");
            foreach(decimal dimension in new decimal[]{ThicknessInches,PlateWidthInches,PlateHeightInches,OffsetXInches,OffsetYInches}) Precision(dimension,6,"Dimension");
            if(ContrastLow<0 || ContrastHigh>255 || ContrastLow>=ContrastHigh || ContrastColors<2 || ContrastColors>256)
                throw new InvalidDataException("Contrast requires low < high, within 0–255, and 2–256 colors.");
            if(StampProfile!="Factory Default 1" || LaserModel!="Aurora" || OutputDirectory==null || OutputDirectory.Length>512 ||
                ColorProfile==null || ColorProfile.Length>64) throw new InvalidDataException("Unsupported model, profile or output location.");
            ClassicColor[] expected=Palette();
            if(Colors==null || Colors.Length!=16) throw new InvalidDataException("Expected the original 16-color palette.");
            for(int i=0;i<16;i++)
            {
                ClassicColor c=Colors[i],e=expected[i];
                if(c==null || c.Name!=e.Name || c.R!=e.R || c.G!=e.G || c.B!=e.B) throw new InvalidDataException("Color palette identity changed.");
                Range(c.PowerPercent,0,100,"Color power");Range(c.SpeedIps,.001M,150,"Color speed");Range(c.Ppi,5,1000,"Color PPI");
                Precision(c.PowerPercent,2,"Color power");Precision(c.SpeedIps,3,"Color speed");
            }
        }
        public string ToXml()
        {
            Validate();
            using(StringWriter writer=new StringWriter(System.Globalization.CultureInfo.InvariantCulture))
            {
                using(XmlWriter xml=XmlWriter.Create(writer,new XmlWriterSettings {OmitXmlDeclaration=true})) new XmlSerializer(typeof(ClassicSettings)).Serialize(xml,this);
                string result=writer.ToString();if(result.Length>15000) throw new InvalidDataException("Settings document exceeds its limit.");return result;
            }
        }
        public string ToPayload() {string result=Convert.ToBase64String(Encoding.UTF8.GetBytes(ToXml()));if(result.Length>20000) throw new InvalidDataException("Settings payload exceeds its limit.");return result;}
        public ClassicSettings Clone() {return FromXml(ToXml());}
        public static ClassicSettings FromPayload(string payload)
        {
            if(payload==null || payload.Length>20000) throw new InvalidDataException("Settings payload exceeds its limit.");
            return FromXml(new UTF8Encoding(false,true).GetString(Convert.FromBase64String(payload)));
        }
        public static ClassicSettings FromXml(string text)
        {
            if(text==null || text.Length>15000) throw new InvalidDataException("Settings document exceeds its limit.");
            XmlDocument document=new XmlDocument {XmlResolver=null};
            using(XmlReader input=XmlReader.Create(new StringReader(text),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=15000})) document.Load(input);
            if(document.DocumentElement.Name!="AuroraPreferences" || document.DocumentElement.NamespaceURI!="") throw new InvalidDataException("Unknown settings document.");
            RequireFields(document.DocumentElement,typeof(ClassicSettings));
            foreach(XmlNode node in document.DocumentElement["Colors"].ChildNodes)
            {if(node is XmlElement) {if(node.Name!="ClassicColor") throw new InvalidDataException("Unknown color record.");RequireFields((XmlElement)node,typeof(ClassicColor));}}
            XmlSerializer serializer=new XmlSerializer(typeof(ClassicSettings));
            serializer.UnknownNode+=delegate(object sender,XmlNodeEventArgs args) {if(args.NodeType!=XmlNodeType.Whitespace) throw new InvalidDataException("Unknown settings field: "+args.Name);};
            serializer.UnknownAttribute+=delegate {throw new InvalidDataException("Unknown settings attribute.");};
            using(XmlReader reader=XmlReader.Create(new StringReader(text),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=15000}))
            {
                ClassicSettings result=(ClassicSettings)serializer.Deserialize(reader);result.Validate();
                // Migrate only the established baseline. Other version-1
                // values were held and their user's intended units are
                // ambiguous: retain the version and value until reselected.
                if(result.Version==1 && result.TravelSpeed==100)
                {result.Version=2;result.TravelSpeed=.100M;}
                return result;
            }
        }
        static void RequireFields(XmlElement element,Type type)
        {
            HashSet<string> required=new HashSet<string>();
            foreach(var field in type.GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance)) required.Add(field.Name);
            foreach(XmlNode node in element.ChildNodes)
                if(node is XmlElement && (node.NamespaceURI!="" || !required.Remove(node.Name))) throw new InvalidDataException("Unknown or duplicate settings field: "+node.Name);
            if(required.Count!=0) throw new InvalidDataException("Incomplete settings snapshot.");
        }
    }

    // One bounded, independently replaceable file per named preset. No arbitrary
    // profile name is ever used as a filesystem path.
    public sealed class ClassicPresets
    {
        readonly string root;
        public ClassicPresets(string root) {this.root=Path.GetFullPath(root);Directory.CreateDirectory(this.root);}
        static string Name(string name)
        {name=(name??"").Trim();if(name.Length<1 || name.Length>64 || name.IndexOfAny(new char[]{'\r','\n','\t'})>=0) throw new ArgumentException("Enter a name of 1–64 characters.");return name;}
        string PathFor(string kind,string name)
        {
            if(kind!="material" && kind!="color") throw new ArgumentException("Unknown preset kind.");
            using(var hash=System.Security.Cryptography.SHA256.Create())
                return Path.Combine(root,kind+"-"+BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Name(name).ToUpperInvariant()))).Replace("-","")+".xml");
        }
        public string[] Names(string kind)
        {
            if(kind!="material" && kind!="color") throw new ArgumentException("Unknown preset kind.");
            List<string> names=new List<string>();
            foreach(string file in Directory.GetFiles(root,kind+"-*.xml"))
            {
                XmlDocument doc=Read(file);names.Add(doc.DocumentElement.GetAttribute("name"));
            }
            names.Sort(StringComparer.OrdinalIgnoreCase);return names.ToArray();
        }
        static XmlDocument Read(string path)
        {
            if(new FileInfo(path).Length>65536) throw new InvalidDataException("Preset file exceeds its limit.");
            XmlDocument doc=new XmlDocument {XmlResolver=null};
            using(XmlReader reader=XmlReader.Create(path,new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=65536})) doc.Load(reader);
            XmlElement element=doc.DocumentElement;
            if(element==null || element.Name!="AuroraPreset" || element.NamespaceURI!="" || element.GetAttribute("version")!="1" || element.Attributes.Count!=2 || !element.HasAttribute("name")) throw new InvalidDataException("Unknown preset document.");
            Name(element.GetAttribute("name"));
            if(element.ChildNodes.Count!=1 || element.FirstChild.Name!="Payload" || element.FirstChild.NamespaceURI!="" || element.FirstChild.Attributes.Count!=0 || element.FirstChild.ChildNodes.Count!=1 || element.FirstChild.FirstChild.NodeType!=XmlNodeType.Text) throw new InvalidDataException("Malformed preset payload.");
            ClassicSettings.FromPayload(element.FirstChild.InnerText);
            return doc;
        }
        public bool Contains(string kind,string name) {return File.Exists(PathFor(kind,name));}
        public void Save(string kind,string name,ClassicSettings settings)
        {
            name=Name(name);string path=PathFor(kind,name);
            if(!File.Exists(path) && Directory.GetFiles(root,kind+"-*.xml").Length>=200) throw new IOException("Keep at most 200 presets of each kind.");
            string payload=settings.ToPayload();
            using(FileStream presetLock=new FileStream(path+".lock",FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
            {
                string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
                try
                {
                    using(FileStream file=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                    {
                        using(XmlWriter writer=XmlWriter.Create(file,new XmlWriterSettings {Indent=true,CloseOutput=false}))
                        {writer.WriteStartElement("AuroraPreset");writer.WriteAttributeString("version","1");writer.WriteAttributeString("name",name);writer.WriteElementString("Payload",payload);writer.WriteEndElement();}
                        file.Flush(true);
                    }
                    if(File.Exists(path)) File.Replace(temp,path,null);else File.Move(temp,path);
                }
                finally {if(File.Exists(temp)) File.Delete(temp);}
            }
        }
        public ClassicSettings Load(string kind,string name)
        {XmlDocument doc=Read(PathFor(kind,name));if(!String.Equals(doc.DocumentElement.GetAttribute("name"),Name(name),StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Preset name changed.");return ClassicSettings.FromPayload(doc.DocumentElement["Payload"].InnerText);}
        public void Delete(string kind,string name)
        {string path=PathFor(kind,name);using(FileStream presetLock=new FileStream(path+".lock",FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None)) File.Delete(path);}
    }
}
