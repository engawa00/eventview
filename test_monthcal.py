import calendar
print(len(calendar.monthcalendar(2023, 2))) # 2023 Feb starts on Wed, ends on Tue (28 days) -> 5 weeks
print(len(calendar.monthcalendar(2023, 4))) # 5 weeks
print(len(calendar.monthcalendar(2015, 2))) # 2015 Feb starts on Sun, ends on Sat (28 days) -> 4 weeks
print(len(calendar.monthcalendar(2023, 10))) # 6 weeks
