using System;
using System.IO;
using System.Windows.Forms;

namespace Aurora.Frontend
{
    public static class ClassicPreferencesProgram
    {
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if(args.Length!=1) throw new ArgumentException("Pass the preview state directory.");
                string root=Path.GetFullPath(args[0]);Directory.CreateDirectory(root);
                string saved=Path.Combine(root,"last-selection.xml");
                ClassicSettings settings=File.Exists(saved)?ClassicSettings.FromXml(File.ReadAllText(saved)):new ClassicSettings();
                Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
                using(ClassicPreferencesForm form=new ClassicPreferencesForm(settings,Path.Combine(root,"presets")))
                {
                    Application.Run(form);
                    if(form.Result!=null) File.WriteAllText(saved,form.Result.ToXml());
                }
                return 0;
            }
            catch(Exception error) {MessageBox.Show(error.Message,"Aurora controls preview",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}
        }
    }
}
