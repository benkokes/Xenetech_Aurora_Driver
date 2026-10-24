using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.Windows.Forms;
using System.Xml;

namespace Aurora.Frontend
{
    public sealed class PreferenceOption
    {
        public string Key;
        public string Label;
        public override string ToString() { return Label; }
    }

    public sealed class PreferenceData
    {
        public static readonly string[] Keys = { "AuroraRasterPower", "AuroraRasterSpeed",
            "AuroraVectorPower", "AuroraVectorSpeed", "AuroraVectorPPI", "AuroraLaserDPI",
            "AuroraAutostart", "AuroraOutputMode", "AuroraFocus" };
        public readonly Dictionary<string,string> Selected = new Dictionary<string,string>();
        public readonly Dictionary<string,List<PreferenceOption>> Options = new Dictionary<string,List<PreferenceOption>>();

        public static PreferenceData Read(string ticketPath,string capabilitiesPath)
        {return FromDocuments(ReadXml(ticketPath),ReadXml(capabilitiesPath));}
        public static PreferenceData ReadXmlText(string ticketXml,string capabilitiesXml)
        {
            XmlDocument ticket=new XmlDocument {XmlResolver=null},capabilities=new XmlDocument {XmlResolver=null};
            XmlReaderSettings settings=new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=1024*1024};
            using(XmlReader reader=XmlReader.Create(new System.IO.StringReader(ticketXml),settings)) ticket.Load(reader);
            using(XmlReader reader=XmlReader.Create(new System.IO.StringReader(capabilitiesXml),settings)) capabilities.Load(reader);
            return FromDocuments(ticket,capabilities);
        }
        static PreferenceData FromDocuments(XmlDocument ticket,XmlDocument capabilities)
        {
            const string framework="http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework";
            PreferenceData data=new PreferenceData();
            foreach(string key in Keys)
            {
                XmlElement cap=FindFeature(capabilities,key),selected=FindFeature(ticket,key);
                List<PreferenceOption> options=new List<PreferenceOption>();
                foreach(XmlNode child in cap.ChildNodes)
                    if(child is XmlElement && child.LocalName=="Option" && child.NamespaceURI==framework)
                    {
                        XmlElement option=(XmlElement)child;
                        string name=PrivateName(option);
                        string label=name;
                        foreach(XmlNode property in option.ChildNodes)
                            if(property is XmlElement && property.LocalName=="Property" &&
                               ((XmlElement)property).GetAttribute("name").EndsWith(":DisplayName",StringComparison.Ordinal))
                                label=property.InnerText;
                        options.Add(new PreferenceOption {Key=name,Label=label});
                    }
                data.Options.Add(key,options);
                foreach(XmlNode child in selected.ChildNodes)
                    if(child is XmlElement && child.LocalName=="Option" && child.NamespaceURI==framework)
                    { data.Selected.Add(key,PrivateName((XmlElement)child)); }
            }
            data.Check(data.Selected);
            return data;
        }

        static XmlDocument ReadXml(string path)
        {
            XmlReaderSettings settings=new XmlReaderSettings { DtdProcessing=DtdProcessing.Prohibit,
                XmlResolver=null,MaxCharactersInDocument=1024*1024 };
            XmlDocument document=new XmlDocument {XmlResolver=null};
            using(XmlReader reader=XmlReader.Create(path,settings)) document.Load(reader);
            return document;
        }

        static string PrivateName(XmlElement element)
        {
            string[] name=element.GetAttribute("name").Split(':');
            if(name.Length!=2 || element.GetNamespaceOfPrefix(name[0])!=NativePreferencesSession.PrivateNamespace)
                throw new InvalidOperationException("Unexpected laser settings namespace.");
            return name[1];
        }

        static XmlElement FindFeature(XmlDocument document,string key)
        {
            foreach(XmlNode child in document.DocumentElement.ChildNodes)
                if(child is XmlElement && child.LocalName=="Feature")
                {
                    XmlElement feature=(XmlElement)child;
                    string[] name=feature.GetAttribute("name").Split(':');
                    if(name.Length==2 && name[1]=="Job"+key &&
                       feature.GetNamespaceOfPrefix(name[0])==NativePreferencesSession.PrivateNamespace) return feature;
                }
            throw new InvalidOperationException("Missing laser setting: "+key);
        }

        public void Check(Dictionary<string,string> selection)
        {
            if (selection.Count != Keys.Length) throw new InvalidOperationException("Incomplete laser settings.");
            foreach (string key in Keys)
            {
                string value;
                if (!selection.TryGetValue(key,out value) || !Options.ContainsKey(key) ||
                    !Options[key].Exists(option => option.Key == value))
                    throw new InvalidOperationException("Unsupported setting: " + key);
            }
        }
    }

    public interface IPreferencesSession
    {
        PreferenceData Data { get; }
        void Save(Dictionary<string,string> selection, Action saved, Action<string> failed);
        void Cancel();
    }

    public sealed class PrinterPreferencesForm : Form
    {
        readonly IPreferencesSession session;
        readonly Dictionary<string,ComboBox> choices = new Dictionary<string,ComboBox>();
        readonly Dictionary<string,NumericUpDown> powers = new Dictionary<string,NumericUpDown>();
        readonly CheckBox autostart = new CheckBox();
        readonly Button okay = new Button();
        readonly Button cancel = new Button();
        readonly Label message = new Label();
        readonly ComboBox material = new ComboBox();
        MaterialProfiles profiles;
        bool busy;
        bool finished;

        public PrinterPreferencesForm(IPreferencesSession session) : this(session,MaterialProfiles.DefaultPath) { }

        public PrinterPreferencesForm(IPreferencesSession session,string profilesPath)
        {
            this.session = session;
            session.Data.Check(session.Data.Selected);
            Text = "Aurora Laser — Printer Properties";
            Font = new Font("Segoe UI",10F);
            AutoScaleMode = AutoScaleMode.Dpi;
            ClientSize = new Size(620,505);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            StartPosition = FormStartPosition.CenterParent;
            ShowInTaskbar = false;

            TabControl tabs=new TabControl {Location=new Point(12,12),Size=new Size(596,410),AccessibleName="Properties tabs"};
            TabPage output=new TabPage("Laser Output Control"),advanced=new TabPage("Advanced"),colors=new TabPage("Color Settings"),about=new TabPage("About");
            tabs.TabPages.AddRange(new TabPage[]{output,advanced,colors,about});Controls.Add(tabs);
            GroupBox raster = new GroupBox {Text="Raster Settings",Location=new Point(14,14),Size=new Size(266,115)};
            GroupBox vector = new GroupBox {Text="Vector Settings",Location=new Point(298,14),Size=new Size(266,155)};
            output.Controls.Add(raster); output.Controls.Add(vector);
            AddPower(raster,"AuroraRasterPower",33);
            AddChoice(raster,"AuroraRasterSpeed","Speed (ips)",72);
            AddPower(vector,"AuroraVectorPower",33);
            AddChoice(vector,"AuroraVectorSpeed","Speed (ips)",72);
            AddChoice(vector,"AuroraVectorPPI","PPI",111);

            GroupBox plate = new GroupBox {Text="Plate and output",Location=new Point(14,185),Size=new Size(550,76)};
            output.Controls.Add(plate);
            plate.Controls.Add(new Label { Text="Plate: 30.00 × 18.00 in     Output: raster and vector",
                AutoSize=true,Location=new Point(14,24) });
            autostart.Text="Start engraving automatically";
            autostart.AccessibleName="Autostart engraving";
            autostart.AutoSize=true;
            autostart.Location=new Point(14,47);
            autostart.Checked=session.Data.Selected["AuroraAutostart"]=="On";
            plate.Controls.Add(autostart);

            GroupBox presets=new GroupBox {Text="Material Setting",Location=new Point(14,276),Size=new Size(550,83)};
            output.Controls.Add(presets);
            material.Location=new Point(14,32);material.Size=new Size(295,27);material.AccessibleName="Material Setting";
            material.DropDownStyle=ComboBoxStyle.DropDown;material.MaxLength=64;presets.Controls.Add(material);
            Button saveMaterial=new Button {Text="Save",Location=new Point(321,30),Size=new Size(96,29)};
            Button deleteMaterial=new Button {Text="Delete",Location=new Point(429,30),Size=new Size(96,29)};
            presets.Controls.Add(saveMaterial);presets.Controls.Add(deleteMaterial);
            try { profiles=new MaterialProfiles(profilesPath,session.Data);RefreshMaterials(""); }
            catch(Exception error) { presets.Enabled=false;message.Text="Materials could not be loaded: "+error.Message; }
            material.SelectionChangeCommitted+=delegate { TryProfile(delegate {ApplySelection(profiles.Get(material.Text));}); };
            saveMaterial.Click+=delegate { TryProfile(delegate {
                string name=MaterialProfiles.CheckName(material.Text);
                if(profiles.Contains(name) && MessageBox.Show(this,"Replace material '"+name+"'?","Material Setting",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return;
                profiles.Save(name,ReadSelection());RefreshMaterials(name);message.Text="Material saved. Click OK to use these settings for this print.";
            }); };
            deleteMaterial.Click+=delegate { TryProfile(delegate {
                string name=MaterialProfiles.CheckName(material.Text);
                if(MessageBox.Show(this,"Delete material '"+name+"'?","Material Setting",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes) return;
                profiles.Delete(name);RefreshMaterials("");message.Text="Material deleted; the current print settings were kept.";
            }); };

            GroupBox laser=new GroupBox {Text="Laser Settings",Location=new Point(14,14),Size=new Size(550,82)};
            advanced.Controls.Add(laser);AddChoice(laser,"AuroraLaserDPI","Resolution (DPI)",32);
            advanced.Controls.Add(new Label {Location=new Point(18,114),Size=new Size(540,90),
                Text="Original resolutions: 50, 100, 167, 200, 250, 333, 500, 1000 and 1200 DPI.\r\n\r\n100 and 167 DPI are available in this build. Other resolutions are being compared with the XP driver before they are enabled."});
            advanced.Controls.Add(new Label {Location=new Point(18,220),Size=new Size(540,115),
                Text="Plate orientation, mirror, bitmap dithering, contrast and rubber-stamp options are not available in this build. They will be added as their output is verified against the original driver."});
            colors.Controls.Add(new Label {Location=new Point(18,22),Size=new Size(540,135),
                Text="Per-color power, speed and PPI, color profiles, vector sorting and pauses between colors are not available in this build.\r\n\r\nThe current print uses the raster and vector settings on Laser Output Control."});
            about.Controls.Add(new Label {Location=new Point(18,22),Size=new Size(540,165),
                Text="Aurora JobServer\r\nXenetech Aurora printer replacement\r\n\r\nMaterial presets are saved for your Windows account. Loading a material edits this dialog; OK attaches a copy of the settings to the print job. Cancel leaves that print's settings unchanged.\r\n\r\nOnly controls supported by this build can be selected."});

            message.Location=new Point(16,426); message.Size=new Size(588,36);
            message.ForeColor=Color.DarkRed; Controls.Add(message);
            okay.Text="OK"; okay.Location=new Point(412,466); okay.Size=new Size(90,28);
            cancel.Text="Cancel"; cancel.Location=new Point(514,466); cancel.Size=new Size(90,28);
            okay.Click += delegate { SaveChanges(); };
            cancel.Click += delegate { CancelChanges(); };
            Controls.Add(okay); Controls.Add(cancel);
            AcceptButton=okay; CancelButton=cancel;
            FormClosing += delegate(object sender, FormClosingEventArgs args) {
                if (busy) { args.Cancel=true; return; }
                if (!finished) { finished=true; session.Cancel(); }
            };
        }

        void RefreshMaterials(string selected)
        { material.Items.Clear();material.Items.AddRange(profiles.Names);material.Text=selected; }

        void TryProfile(Action action)
        { try { action(); } catch(Exception error) { message.Text=error.Message; } }

        public void ApplySelection(Dictionary<string,string> selection)
        {
            session.Data.Check(selection);
            foreach(var item in powers) item.Value.Value=Int32.Parse(selection[item.Key].Substring(7),CultureInfo.InvariantCulture);
            foreach(var item in choices)
                foreach(PreferenceOption option in item.Value.Items)
                    if(option.Key==selection[item.Key]) {item.Value.SelectedItem=option;break;}
            autostart.Checked=selection["AuroraAutostart"]=="On";
        }

        void AddLabel(Control parent,string text,int y)
        { parent.Controls.Add(new Label {Text=text,AutoSize=true,Location=new Point(14,y+4)}); }

        void AddPower(Control parent,string key,int y)
        {
            AddLabel(parent,"Power (%)",y);
            for (int n=0;n<=100;n++)
                if (!session.Data.Options[key].Exists(option=>option.Key=="Percent"+n))
                    throw new InvalidOperationException("Power range is unavailable.");
            NumericUpDown input=new NumericUpDown { Minimum=0,Maximum=100,DecimalPlaces=0,
                Location=new Point(146,y),Size=new Size(104,27),AccessibleName=key };
            input.Value=Int32.Parse(session.Data.Selected[key].Substring(7),CultureInfo.InvariantCulture);
            powers.Add(key,input); parent.Controls.Add(input);
        }

        void AddChoice(Control parent,string key,string label,int y)
        {
            AddLabel(parent,label,y);
            ComboBox input=new ComboBox {DropDownStyle=ComboBoxStyle.DropDownList,
                Location=new Point(146,y),Size=new Size(104,27),AccessibleName=key};
            foreach(PreferenceOption option in session.Data.Options[key])
            {
                input.Items.Add(option);
                if(option.Key==session.Data.Selected[key]) input.SelectedItem=option;
            }
            choices.Add(key,input); parent.Controls.Add(input);
        }

        public Dictionary<string,string> ReadSelection()
        {
            // Editing controls never changes the caller's ticket. Apply only on OK.
            Dictionary<string,string> result=new Dictionary<string,string>(session.Data.Selected);
            foreach(var item in powers) result[item.Key]="Percent"+item.Value.Value.ToString(CultureInfo.InvariantCulture);
            foreach(var item in choices)
            {
                PreferenceOption option=item.Value.SelectedItem as PreferenceOption;
                if(option==null) throw new InvalidOperationException("Choose a value for "+item.Key);
                result[item.Key]=option.Key;
            }
            result["AuroraAutostart"]=autostart.Checked ? "On" : "Off";
            session.Data.Check(result);
            return result;
        }

        public void SaveChanges()
        {
            if (busy || finished) return;
            try
            {
                Dictionary<string,string> selection=ReadSelection();
                SetBusy(true); message.Text="";
                session.Save(selection,delegate { OnUi(delegate { SetBusy(false); finished=true; Close(); }); },
                    error=>OnUi(delegate { SetBusy(false); message.Text=error; }));
            }
            catch(Exception error) { SetBusy(false); message.Text=error.Message; }
        }

        public void CancelChanges()
        {
            if(busy || finished) return;
            finished=true; session.Cancel(); Close();
        }

        void SetBusy(bool value)
        { busy=value; okay.Enabled=!value; cancel.Enabled=!value; }

        void OnUi(Action action)
        { if(!IsDisposed) { if(InvokeRequired) BeginInvoke(action); else action(); } }
    }
}
