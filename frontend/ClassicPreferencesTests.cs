using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Windows.Forms;

namespace Aurora.Frontend
{
    public static class ClassicPreferencesTests
    {
        static void Check(bool condition,string message) {if(!condition) throw new InvalidOperationException(message);}
        static int count;
        static void Run(string name,Action action) {action();count++;Console.WriteLine("PASS "+name);}
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                string root=Path.GetFullPath(args[0]);Directory.CreateDirectory(root);
                // Preset filenames include hashes and atomic-save suffixes.
                // Keep disposable test stores off a possibly deep report path.
                string temporaryRoot=Path.GetFullPath(Path.GetTempPath());
                string scratch=Path.GetFullPath(Path.Combine(temporaryRoot,"aurora-controls-"+Guid.NewGuid().ToString("N")));
                if(!scratch.StartsWith(temporaryRoot.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Test store escaped temporary root.");
                Directory.CreateDirectory(scratch);
                Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
                Run("all original controls survive a complete immutable payload",delegate {
                    ClassicSettings original=new ClassicSettings();
                    original.UseColors=true;original.PauseColors=true;original.BottomUp=true;original.Output=ClassicOutput.VectorOnly;
                    original.Focus=ClassicFocus.Thickness;original.ThicknessInches=.125M;original.Mirror=true;original.Orientation=ClassicOrientation.Right90;
                    original.ManualContrast=true;original.ContrastLow=10;original.ContrastHigh=230;original.ContrastColors=32;
                    original.Colors[11].PowerPercent=42;original.Colors[11].SpeedIps=5.125M;original.Colors[2].Enabled=false;
                    ClassicSettings restored=ClassicSettings.FromPayload(original.ToPayload());
                    Check(restored.ToXml()==original.ToXml(),"Full settings payload changed.");
                    restored.Colors[11].PowerPercent=1;Check(original.Colors[11].PowerPercent==42,"Snapshot shares a mutable color record.");
                });
                Run("incomplete unknown duplicate and hostile settings are rejected",delegate {
                    string xml=new ClassicSettings().ToXml();
                    foreach(string malformed in new string[]{"<AuroraPreferences/>",xml.Replace("<Version>2</Version>","<Version>2</Version><Version>2</Version>"),
                        xml.Replace("<Version>2</Version>",""),xml.Replace("<Version>2</Version>","<Unknown>1</Unknown>"),
                        "<!DOCTYPE AuroraPreferences [<!ENTITY x SYSTEM 'file:///missing'>]>"+xml})
                    {
                        bool rejected=false;try {ClassicSettings.FromXml(malformed);} catch(Exception) {rejected=true;}
                        Check(rejected,"Malformed settings were accepted.");
                    }
                });
                Run("legacy baseline migration preserves process settings and unverified legacy travel stays explicit",delegate {
                    ClassicSettings legacy=new ClassicSettings {Version=1,TravelSpeed=100,RasterPower=46,VectorPower=16};
                    ClassicSettings migrated=ClassicSettings.FromPayload(legacy.ToPayload());
                    Check(migrated.Version==2 && migrated.TravelSpeed==.100M && migrated.RasterPower==46 && migrated.VectorPower==16,"Legacy baseline migrated incorrectly.");
                    Check(ClassicSettings.FromXml(migrated.ToXml()).ToXml()==migrated.ToXml(),"Migration is not idempotent.");
                    foreach(decimal value in new decimal[]{.001M,.1M,1M,90M,250M})
                    {
                        legacy.TravelSpeed=value;
                        ClassicSettings retained=ClassicSettings.FromXml(legacy.ToXml());
                        Check(retained.Version==1 && retained.TravelSpeed==value,"Ambiguous legacy travel was silently reinterpreted.");
                    }
                    ClassicPresets presets=new ClassicPresets(Path.Combine(scratch,"legacy-presets"));
                    legacy.TravelSpeed=100;presets.Save("material","Legacy accepted baseline",legacy);
                    ClassicSettings loaded=presets.Load("material","Legacy accepted baseline");
                    Check(loaded.Version==2 && loaded.TravelSpeed==.1M && loaded.RasterPower==46 && loaded.VectorPower==16,"Legacy material did not migrate without changing powers.");
                    legacy.TravelSpeed=.1M;presets.Save("material","Legacy held value",legacy);
                    loaded=presets.Load("material","Legacy held value");
                    Check(loaded.Version==1 && loaded.TravelSpeed==.1M,"Loading a held preset silently made it the supported ips baseline.");
                });
                Run("full material and color presets retain values without changing originals",delegate {
                    ClassicPresets presets=new ClassicPresets(Path.Combine(scratch,"store"));ClassicSettings settings=new ClassicSettings();
                    settings.Colors[0].PowerPercent=32;settings.BitmapMode=ClassicBitmap.Photo;settings.Focus=ClassicFocus.Manual;
                    presets.Save("material","Birch / <sample>",settings);presets.Save("color","Colors <one>",settings);
                    settings.Colors[0].PowerPercent=1;
                    Check(presets.Load("material","birch / <sample>").Colors[0].PowerPercent==32,"Saved preset mutated.");
                    Check(presets.Load("color","Colors <one>").Focus==ClassicFocus.Manual,"Preset lost fields.");
                    presets.Delete("material","Birch / <sample>");Check(presets.Names("material").Length==0 && presets.Names("color").Length==1,"Preset kinds were mixed.");
                });
                Run("complete settings and native carrier options cannot conflict",delegate {
                    ClassicSettings settings=new ClassicSettings();settings.RasterPower=45.25M;settings.VectorSpeed=12.345M;settings.VectorPpi=777;
                    var selection=ClassicTicket.Carriers(settings);
                    Check(selection["AuroraRasterPower"]=="Custom" && selection["AuroraVectorSpeed"]=="Custom" && selection["AuroraVectorPPI"]=="Custom","Arbitrary controls were rounded to old options.");
                    string xml="<psf:PrintTicket xmlns:psf=\""+ClassicTicket.Framework+"\" version=\"1\">"+ClassicTicket.ParameterXml(settings)+"</psf:PrintTicket>";
                    Check(ClassicTicket.Read(xml,selection).ToXml()==settings.ToXml(),"Ticket lost complete settings.");
                    selection["AuroraRasterPower"]="Percent45";bool rejected=false;
                    try {ClassicTicket.Read(xml,selection);} catch(InvalidDataException) {rejected=true;}
                    Check(rejected,"Conflicting ticket controls were accepted.");
                });
                Run("native save failure keeps the window open and retry commits the snapshot",delegate {
                    int calls=0;
                    using(ClassicPreferencesForm form=new ClassicPreferencesForm(new ClassicSettings(),Path.Combine(scratch,"native-presets"),
                        delegate(ClassicSettings state,Action saved,Action<string> failed) {calls++;if(calls==1) failed("Synthetic validation failure");else saved();}))
                    {
                        form.StartPosition=FormStartPosition.Manual;form.Location=new Point(-10000,-10000);form.Show();Application.DoEvents();
                        form.Raster.Power.Value=46;form.SaveChanges();
                        Check(form.Result==null && form.Visible,"Failed save closed the settings window.");
                        form.SaveChanges();Check(calls==2 && form.Result.RasterPower==46,"Retry lost the chosen settings.");
                    }
                });
                using(ClassicPreferencesForm form=new ClassicPreferencesForm(new ClassicSettings(),Path.Combine(scratch,"form-presets")))
                {
                    form.StartPosition=FormStartPosition.Manual;form.Location=new Point(-10000,-10000);form.Show();Application.DoEvents();
                    Run("travel control shows ips and does not reinterpret a legacy value without an explicit edit",delegate {
                        NumericUpDown travel=(NumericUpDown)form.Named("TravelSpeed");
                        Check(travel.Value==.100M && form.ReadSettings().Version==2,"Default travel is not 0.100 ips.");
                        form.ApplySettings(new ClassicSettings {Version=1,TravelSpeed=90,RasterPower=46});
                        form.Raster.Power.Value=47;
                        Check(form.ReadSettings().Version==1 && form.ReadSettings().TravelSpeed==90,"Unrelated edit unlocked legacy travel.");
                        travel.Value=1;
                        Check(form.ReadSettings().Version==2 && form.ReadSettings().TravelSpeed==1 && form.ReadSettings().RasterPower==47,"Explicit travel reselection lost settings or units.");
                        form.ApplySettings(new ClassicSettings {Version=1,TravelSpeed=100});
                        Check(travel.Value==.100M && form.ReadSettings().Version==2,"Legacy baseline was displayed as 100 ips.");
                        form.ApplySettings(new ClassicSettings());
                    });
                    Run("output focus plate and advanced bindings retain edits",delegate {
                        ((RadioButton)form.Named("Output"+ClassicOutput.RasterOnly)).Checked=true;
                        ((CheckBox)form.Named("UseColors")).Checked=true;
                        Check(form.Named("SortColors").Enabled && form.Named("PauseColors").Enabled,"Color dependencies missing.");
                        ((RadioButton)form.Named("Focus"+ClassicFocus.Thickness)).Checked=true;
                        Check(form.Named("ThicknessInches").Enabled,"Thickness control is still disabled.");
                        ((NumericUpDown)form.Named("ThicknessInches")).Value=.125M;
                        ((NumericUpDown)form.Named("PlateWidthInches")).Value=12;
                        ((NumericUpDown)form.Named("OffsetXInches")).Value=.123M;
                        ((CheckBox)form.Named("InvertRaster")).Checked=true;
                        ((RadioButton)form.Named("BitmapMode"+ClassicBitmap.Custom)).Checked=true;
                        ((CheckBox)form.Named("DitherBitmaps")).Checked=true;
                        ((RadioButton)form.Named("Dither"+ClassicDither.Jarvis)).Checked=true;
                        Check(((RadioButton)form.Named("BitmapMode"+ClassicBitmap.Custom)).Checked,"Dither radios changed bitmap mode.");
                        ((CheckBox)form.Named("ManualContrast")).Checked=true;
                        ((NumericUpDown)form.Named("ContrastLow")).Value=10;
                        ((RadioButton)form.Named("Orientation"+ClassicOrientation.Left90)).Checked=true;
                        ((RadioButton)form.Named("MirrorTrue")).Checked=true;
                        ClassicSettings settings=form.ReadSettings();
                        Check(settings.Output==ClassicOutput.RasterOnly && settings.Focus==ClassicFocus.Thickness && settings.ThicknessInches==.125M,"Output/focus edits lost.");
                        Check(settings.PlateWidthInches==12 && settings.OffsetXInches==.123M && settings.InvertRaster,"Plate/output edits lost.");
                        Check(settings.Dither==ClassicDither.Jarvis && settings.ManualContrast && settings.ContrastLow==10 && settings.Mirror && settings.Orientation==ClassicOrientation.Left90,"Advanced edits lost.");
                    });
                    Run("unit toggles preserve canonical dimensions and boundary values",delegate {
                        ClassicSettings settings=form.ReadSettings();settings.PlateWidthInches=.001M;settings.ThicknessInches=.001M;
                        form.ApplySettings(settings);form.ToggleUnits();form.ToggleUnits();
                        Check(form.ReadSettings().PlateWidthInches==.001M && form.ReadSettings().ThicknessInches==.001M,"Unit switch rounded canonical values.");
                    });
                    Run("selected-color editing updates the matching palette row",delegate {
                        form.SelectedColorEditor.Power.Value=44;form.SelectedColorEditor.Speed.Value=22.125M;form.SelectedColorEditor.Ppi.Value=777;
                        ClassicColor selected=form.ReadSettings().Colors[11];
                        Check(selected.Name=="Silver" && selected.PowerPercent==44 && selected.SpeedIps==22.125M && selected.Ppi==777,"Color editor was not stored.");
                    });
                    form.ApplySettings(new ClassicSettings());
                    Run("tab navigation preserves the selected color and its edits",delegate {
                        form.Tabs.SelectedIndex=2;Application.DoEvents();
                        Check(form.ColorGrid.CurrentCell.RowIndex==11 && form.SelectedColorEditor.Power.Value==45,"Tab activation changed the selected color.");
                        form.SelectedColorEditor.Power.Value=43;
                        form.ColorGrid.CurrentCell=form.ColorGrid.Rows[1].Cells[2];Application.DoEvents();
                        Check(form.SelectedColorEditor.Power.Value==95 && form.ReadSettings().Colors[11].PowerPercent==43,"Color selection lost or reassigned edits.");
                        form.Tabs.SelectedIndex=0;form.Tabs.SelectedIndex=2;Application.DoEvents();
                        Check(form.ColorGrid.CurrentCell.RowIndex==1 && form.SelectedColorEditor.Power.Value==95,"Reopening Colors changed the selection.");
                        form.ColorGrid.CurrentCell=form.ColorGrid.Rows[11].Cells[2];form.ApplySettings(new ClassicSettings());
                    });
                    Run("all three full pages render with their original controls",delegate {
                        for(int i=0;i<3;i++)
                        {
                            form.Tabs.SelectedIndex=i;Application.DoEvents();
                            using(Bitmap bitmap=new Bitmap(form.Width,form.Height))
                            {form.DrawToBitmap(bitmap,new Rectangle(Point.Empty,form.Size));bitmap.Save(Path.Combine(root,"classic-tab-"+i+".png"),ImageFormat.Png);}
                        }
                    });
                    Run("all sixteen palette rows edit and retain their own checkbox and process values",delegate {
                        form.ApplySettings(new ClassicSettings());form.Tabs.SelectedIndex=2;Application.DoEvents();
                        for(int i=0;i<16;i++)
                        {
                            form.ColorGrid.CurrentCell=form.ColorGrid.Rows[i].Cells[2];Application.DoEvents();
                            form.SelectedColorEditor.Power.Value=10M+i+.25M;
                            form.SelectedColorEditor.Speed.Value=.001M+i;
                            form.SelectedColorEditor.Ppi.Value=5+i;
                            form.ColorGrid.Rows[i].Cells[0].Value=(i%2==0);
                        }
                        ClassicSettings saved=form.ReadSettings();
                        for(int i=0;i<16;i++)
                        {
                            ClassicColor c=saved.Colors[i];
                            Check(c.PowerPercent==10M+i+.25M && c.SpeedIps==.001M+i && c.Ppi==5+i && c.Enabled==(i%2==0),"Palette row "+i+" inherited another row's edit.");
                        }
                        Check(saved.RasterPower==45 && saved.VectorPower==15 && !saved.UseColors,"Palette editing changed global process controls.");
                    });
                    Run("displayed decimal limits and repeated unit toggles preserve canonical settings",delegate {
                        ClassicSettings expected=new ClassicSettings {RasterPower=99.99M,RasterSpeed=149.999M,VectorPower=.01M,VectorSpeed=.001M,VectorPpi=5,
                            ThicknessInches=.123456M,PlateWidthInches=12.345678M,PlateHeightInches=9.876543M,OffsetXInches=-.123456M,OffsetYInches=.123456M};
                        form.ApplySettings(expected);
                        for(int i=0;i<50;i++) form.ToggleUnits();
                        Check(form.ReadSettings().ToXml()==expected.ToXml(),"Displaying/toggling units rounded untouched canonical values.");
                        form.Raster.Power.Value=100;form.Vector.Power.Value=0;form.Vector.Speed.Value=15;form.Vector.Ppi.Value=1000;
                        ClassicSettings changed=form.ReadSettings();
                        Check(changed.RasterPower==100 && changed.VectorPower==0 && changed.VectorSpeed==15 && changed.VectorPpi==1000,"Process limits did not survive their sliders.");
                    });
                    Run("inactive controls retain values while bitmap and color dependencies change",delegate {
                        ClassicSettings expected=new ClassicSettings {Dither=ClassicDither.Stucki,DitherBitmaps=true,ManualContrast=true,ContrastLow=12,ContrastHigh=230,ContrastColors=17,
                            SortColors=false,PauseColors=true,ThicknessInches=.125M};
                        form.ApplySettings(expected);
                        ((RadioButton)form.Named("BitmapMode"+ClassicBitmap.Photo)).Checked=true;
                        Check(!form.Named("DitherBitmaps").Enabled && !form.Named("ContrastLow").Enabled,"Photo left custom controls active.");
                        ((RadioButton)form.Named("BitmapMode"+ClassicBitmap.Custom)).Checked=true;
                        Check(form.Named("Dither"+ClassicDither.Stucki).Enabled && form.Named("ContrastLow").Enabled,"Custom did not restore dependencies.");
                        ((CheckBox)form.Named("UseColors")).Checked=true;((CheckBox)form.Named("UseColors")).Checked=false;
                        ((RadioButton)form.Named("Focus"+ClassicFocus.Thickness)).Checked=true;((RadioButton)form.Named("Focus"+ClassicFocus.None)).Checked=true;
                        Check(form.ReadSettings().ToXml()==expected.ToXml(),"Disabling a control discarded its stored value.");
                    });
                    form.Close();Check(form.Result==null,"Cancel/close committed a preview.");
                }
                if(!Path.GetFullPath(scratch).StartsWith(temporaryRoot.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Refusing cleanup outside temporary root.");
                Directory.Delete(scratch,true);
                File.WriteAllText(Path.Combine(root,"default-settings.xml"),new ClassicSettings().ToXml());
                Console.WriteLine(count+" complete-controls checks passed; no printer or laser was changed.");return 0;
            }
            catch(Exception error) {Console.Error.WriteLine(error);return 1;}
        }
    }
}
