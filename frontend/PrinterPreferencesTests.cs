using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Printing;
using System.Windows.Forms;
using System.Xml;

namespace Aurora.Frontend
{
    public static class PrinterPreferencesTests
    {
        sealed class Session : IPreferencesSession
        {
            public PreferenceData Values;
            public Dictionary<string,string> Saved;
            public int Cancellations;
            public PreferenceData Data { get { return Values; } }
            public void Save(Dictionary<string,string> selection,Action saved,Action<string> failed)
            { Saved=new Dictionary<string,string>(selection); saved(); }
            public void Cancel() { Cancellations++; }
        }

        static Control Find(Control parent,string name)
        {
            foreach(Control child in parent.Controls)
            {
                if(child.AccessibleName==name) return child;
                Control match=Find(child,name); if(match!=null) return match;
            }
            return null;
        }

        static void Require(bool condition,string description)
        { if(!condition) throw new InvalidOperationException(description); }

        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                string ticket=Path.Combine(args[0],"default-printticket.xml");
                string caps=Path.Combine(args[0],"printcapabilities.xml");
                PreferenceData original=PreferenceData.Read(ticket,caps);
                Require(original.Selected["AuroraRasterPower"]=="Percent45" &&
                        original.Selected["AuroraVectorPower"]=="Percent15","Native defaults differ.");

                Session session=new Session {Values=original};
                string temporary=Path.Combine(Path.GetTempPath(),"AuroraMaterials-"+Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(temporary);
                string profilesPath=Path.Combine(temporary,"materials.xml");
                Dictionary<string,string> changed;
                using(PrinterPreferencesForm form=new PrinterPreferencesForm(session,profilesPath))
                {
                    TabControl tabs=(TabControl)Find(form,"Properties tabs");
                    Require(tabs.TabPages.Count==4 && tabs.TabPages[0].Text=="Laser Output Control" &&
                            tabs.TabPages[1].Text=="Advanced" && tabs.TabPages[2].Text=="Color Settings","Original tab layout missing.");
                    string previews=Path.Combine(Path.GetDirectoryName(args[0]),"printer-properties-tab-preview");
                    Directory.CreateDirectory(previews);
                    form.StartPosition=FormStartPosition.Manual;form.Location=new Point(-10000,-10000);
                    form.Show();Application.DoEvents();
                    for(int i=0;i<tabs.TabPages.Count;i++)
                    {
                        tabs.SelectedIndex=i;Application.DoEvents();
                        using(Bitmap bitmap=new Bitmap(form.Width,form.Height))
                        { form.DrawToBitmap(bitmap,new Rectangle(Point.Empty,form.Size));bitmap.Save(Path.Combine(previews,"tab-"+i+".png"),ImageFormat.Png); }
                    }
                    tabs.SelectedIndex=0;
                    Require(form.ReadSelection().Count==9,"The form lost fixed laser features.");
                    ((NumericUpDown)Find(form,"AuroraRasterPower")).Value=46;
                    ((NumericUpDown)Find(form,"AuroraVectorPower")).Value=16;
                    Require(session.Saved==null && original.Selected["AuroraRasterPower"]=="Percent45",
                            "Editing a control changed the caller before OK.");
                    changed=form.ReadSelection();
                    Require(changed["AuroraRasterPower"]=="Percent46" && changed["AuroraVectorPower"]=="Percent16",
                            "Displayed power values did not map to native options.");
                    foreach(string key in PreferenceData.Keys)
                        if(key!="AuroraRasterPower" && key!="AuroraVectorPower")
                            Require(changed[key]==original.Selected[key],"Unedited setting changed: "+key);
                    form.SaveChanges();
                    Require(session.Saved!=null && session.Saved["AuroraVectorPower"]=="Percent16" &&
                            session.Cancellations==0,"OK failed to save the chosen values.");
                }
                session=new Session {Values=PreferenceData.Read(ticket,caps)};
                using(PrinterPreferencesForm form=new PrinterPreferencesForm(session,profilesPath))
                {
                    ((NumericUpDown)Find(form,"AuroraRasterPower")).Value=70;
                    form.CancelChanges();
                    Require(session.Saved==null && session.Cancellations==1 &&
                            session.Data.Selected["AuroraRasterPower"]=="Percent45","Cancel changed the print settings.");
                }

                MaterialProfiles presets=new MaterialProfiles(profilesPath,original);
                MaterialProfiles stale=new MaterialProfiles(profilesPath,original);
                presets.Save("Birch / test <1>",changed);
                changed["AuroraRasterPower"]="Percent47";
                Require(presets.Get("birch / test <1>")["AuroraRasterPower"]=="Percent46","Preset was changed by a caller mutation.");
                MaterialProfiles restored=new MaterialProfiles(profilesPath,original);
                Require(restored.Get("Birch / test <1>")["AuroraVectorPower"]=="Percent16","Preset did not survive reload.");
                bool rejected=false;
                try { stale.Save("Stale",original.Selected); } catch(IOException) { rejected=true; }
                Require(rejected && !stale.Contains("Stale"),"A stale Properties window overwrote saved materials.");
                using(PrinterPreferencesForm form=new PrinterPreferencesForm(session,profilesPath))
                {
                    form.ApplySelection(restored.Get("Birch / test <1>"));
                    Require(form.ReadSelection()["AuroraRasterPower"]=="Percent46","Loading a material did not update controls.");
                    form.CancelChanges();
                    Require(session.Saved==null && session.Data.Selected["AuroraRasterPower"]=="Percent45","Loading a preset changed the caller on Cancel.");
                }
                changed["AuroraRasterPower"]="Percent46";
                restored.Delete("Birch / test <1>");
                Require(new MaterialProfiles(profilesPath,original).Names.Length==0,"Material deletion did not persist.");
                byte[] invalid=System.Text.Encoding.UTF8.GetBytes("<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///nonexistent'>]><AuroraMaterialProfiles version='1'>&e;</AuroraMaterialProfiles>");
                File.WriteAllBytes(profilesPath,invalid);rejected=false;
                try { new MaterialProfiles(profilesPath,original); } catch(XmlException) { rejected=true; }
                Require(rejected && File.ReadAllBytes(profilesPath).Length==invalid.Length,"Invalid profile data was accepted or replaced.");
                Directory.Delete(temporary,true);

                // Exercise the installed Windows provider with the form's actual
                // selection. This validates in memory; it never changes defaults
                // or submits a print job.
                const string psf="http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework";
                XmlDocument delta=new XmlDocument();
                XmlElement root=delta.CreateElement("psf","PrintTicket",psf);
                root.SetAttribute("version","1");
                root.SetAttribute("xmlns:aur",NativePreferencesSession.PrivateNamespace);
                delta.AppendChild(root);
                foreach(string key in PreferenceData.Keys)
                {
                    XmlElement feature=delta.CreateElement("psf","Feature",psf);
                    feature.SetAttribute("name","aur:Job"+key);
                    XmlElement option=delta.CreateElement("psf","Option",psf);
                    option.SetAttribute("name","aur:"+changed[key]);
                    feature.AppendChild(option);root.AppendChild(feature);
                }
                string output=Path.Combine(Path.GetDirectoryName(args[0]),"printer-properties-tests");
                Directory.CreateDirectory(output);
                string mergedPath=Path.Combine(output,"validated-46-16.xml");
                using(LocalPrintServer server=new LocalPrintServer())
                using(PrintQueue queue=server.GetPrintQueue("Aurora JobServer (Test Capture)"))
                using(MemoryStream bytes=new MemoryStream(System.Text.Encoding.UTF8.GetBytes(delta.OuterXml)))
                {
                    PrintTicket proposed=new PrintTicket(bytes);
                    ValidationResult validated=queue.MergeAndValidatePrintTicket(queue.DefaultPrintTicket,proposed,PrintTicketScope.JobScope);
                    using(Stream source=validated.ValidatedPrintTicket.GetXmlStream())
                    using(Stream destination=File.Create(mergedPath)) source.CopyTo(destination);
                    PreferenceData native=PreferenceData.Read(mergedPath,caps);
                    foreach(string key in PreferenceData.Keys)
                        Require(native.Selected[key]==changed[key],"Windows did not preserve chosen value: "+key);
                }
                Console.WriteLine("Printer Properties: native defaults, XP tabs, material preset roundtrip/load/Cancel/delete/concurrent-edit guards, XML rejection, OK, Cancel, and Windows 46/16 validation passed. No print submitted.");
                return 0;
            }
            catch(Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
