Set service = CreateObject("Schedule.Service")
service.Connect()
Set rootFolder = service.GetFolder("\")
Set taskDefinition = service.NewTask(0)
Set regInfo = taskDefinition.RegistrationInfo
regInfo.Description = "热点信息差自动更新 - 每3小时"
Set settings = taskDefinition.Settings
settings.Enabled = True
settings.StartWhenAvailable = True
settings.AllowHardTerminate = True
settings.ExecutionTimeLimit = "PT1H"
Set triggers = taskDefinition.Triggers
Set trigger = triggers.Create(1)
trigger.DaysInterval = 1
trigger.StartBoundary = "2026-07-06T00:00:00"
trigger.Repetition.Interval = "PT3H"
trigger.Repetition.Duration = "P365D"
trigger.Enabled = True
Set action = taskDefinition.Actions.Create(0)
action.Path = "D:\AI\hotinfo\hot-info\auto_run.bat"
action.WorkingDirectory = "D:\AI\hotinfo\hot-info"
Set principal = taskDefinition.Principal
principal.UserId = "SYSTEM"
principal.LogonType = 5
principal.RunLevel = 1
rootFolder.RegisterTaskDefinition "HotInfoAutoUpdate", taskDefinition, 6, "", "", 5
WScript.Echo "Task created successfully!"
